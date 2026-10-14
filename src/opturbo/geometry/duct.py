"""Builders for the airfoil and lower-PARSEC flanged duct profiles."""

import math

import Part
from FreeCAD import Base

from .config import DesignParameters
from .freecad_helpers import checked
from .parsec import coefficients, profile, surface
from ..parsec import lower_profile


PARSEC_DUCT = {
    "upper": {"leading_edge_radius": 0.0162187, "crest_location": 0.376723,
              "crest_height": 0.101977, "crest_curvature": -1.11136,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": -12.9184},
    "lower": {"leading_edge_radius": 0.00748922, "crest_location": 0.360,
              "crest_height": -0.11, "crest_curvature": 1.64354,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": 0.148211},
}


def _edge_samples(edge):
    """Discretize an offset edge while retaining its endpoints."""
    return list(edge.discretize(Number=max(3, min(4000, int(edge.Length / 0.25) + 3))))


def _join_edge_route(edges, indices, start_cap, end_cap):
    """Combine consecutive offset edges into one filling boundary curve."""
    route = [edges[index] for index in indices]
    if not route:
        raise RuntimeError("Offset boundary has an empty side between end caps.")
    samples = _edge_samples(route[0])
    cap_vertices = [vertex.Point for vertex in start_cap.Vertexes]
    current = min((samples[0], samples[-1]),
                  key=lambda point: min((point.sub(v).Length for v in cap_vertices), default=0))
    joined = [current]
    for edge in route:
        points = _edge_samples(edge)
        if points[-1].sub(current).Length < points[0].sub(current).Length:
            points.reverse()
        if points[0].sub(current).Length > 1e-5:
            raise RuntimeError("Offset boundary edges are not connected in order.")
        joined.extend(point for point in points[1:] if point.sub(joined[-1]).Length > 1e-7)
        current = joined[-1]
    end_vertices = [vertex.Point for vertex in end_cap.Vertexes]
    if min((current.sub(point).Length for point in end_vertices), default=1) > 1e-5:
        raise RuntimeError("Offset boundary does not meet its end cap.")
    curve = Part.BSplineCurve()
    curve.interpolate(joined)
    return curve.toShape()


def _surface_filled_face(document, wire, start_center, end_center, half_width):
    """Fill the native offset boundary from its two sides and round caps."""
    edges = list(wire.Edges)
    cap_indices = {}
    for label, center in (("start", start_center), ("end", end_center)):
        candidates = []
        for index, edge in enumerate(edges):
            curve = edge.Curve
            if hasattr(curve, "Center") and hasattr(curve, "Radius"):
                distance = curve.Center.sub(center).Length
                if distance < max(1e-5, half_width * 1e-4):
                    candidates.append((distance, index))
        if not candidates:
            raise RuntimeError(f"Offset wire is missing its rounded {label} cap.")
        cap_indices[label] = min(candidates)[1]
    start_index, end_index = cap_indices["start"], cap_indices["end"]

    def between(first, last):
        result, index = [], (first + 1) % len(edges)
        while index != last:
            result.append(index)
            index = (index + 1) % len(edges)
        return result

    side_a = _join_edge_route(edges, between(end_index, start_index), edges[end_index], edges[start_index])
    side_b = _join_edge_route(edges, between(start_index, end_index), edges[start_index], edges[end_index])
    boundary = document.addObject("Part::Feature", "DuctBoundary")
    boundary.Shape = Part.Compound([side_a, edges[start_index].copy(), side_b, edges[end_index].copy()])
    document.recompute()
    filling = document.addObject("Surface::Filling", "DuctSurface")
    filling.BoundaryEdges = [(boundary, f"Edge{index}") for index in range(1, 5)]
    document.recompute()
    return checked(filling.Shape.copy(), "Surface Filling duct face")


def _airfoil_duct(parameters: DesignParameters):
    """Build the original closed PARSEC airfoil as a planar face."""
    x_values, upper, lower = profile(parameters.duct_points, parameters.parsec)
    if parameters.duct_reverse:
        upper, lower = [-value for value in upper], [-value for value in lower]
    angle = math.tan(math.radians(parameters.duct_angle_deg))
    top, bottom = [], []
    for x, y_upper, y_lower in zip(x_values, upper, lower):
        axial = parameters.duct_origin_x + parameters.duct_chord * x
        centre = parameters.duct_origin_r + parameters.duct_chord * x * angle
        top.append(Base.Vector(axial, centre + parameters.duct_chord * y_upper, 0))
        bottom.append(Base.Vector(axial, centre + parameters.duct_chord * y_lower, 0))
    upper_curve, lower_curve = Part.BSplineCurve(), Part.BSplineCurve()
    upper_curve.interpolate(top)
    lower_curve.interpolate(list(reversed(bottom)))
    wire = Part.Wire([upper_curve.toShape(), lower_curve.toShape()])
    return checked(Part.Face(wire), "PARSEC duct face")


def _flanged_duct(parameters: DesignParameters):
    """Build the five-term flanged contour with native FreeCAD offset/filling."""
    x_values, values = lower_profile({"lower": parameters.flanged_curve}, parameters.duct_points)
    if parameters.duct_reverse:
        values = [-value for value in values]
    points = [Base.Vector(parameters.duct_origin_x + parameters.duct_chord * x,
                          parameters.duct_origin_r + parameters.duct_chord * y, 0)
              for x, y in zip(x_values, values)]
    tail = points[-1]
    angle = math.radians(parameters.duct_flange_angle_deg)
    flange_end = Base.Vector(tail.x + parameters.duct_flange_length * math.cos(angle),
                             tail.y + parameters.duct_flange_length * math.sin(angle), 0)
    curve = Part.BSplineCurve()
    curve.interpolate(points)
    path = Part.Wire([curve.toShape(), Part.LineSegment(tail, flange_end).toShape()])

    import FreeCAD as App
    document = App.newDocument("temporary_duct_offset")
    try:
        source = document.addObject("Part::Feature", "DuctCenterPath")
        source.Shape = path
        offset = document.addObject("Part::Offset2D", "DuctOffset")
        offset.Source = source
        offset.Value = parameters.duct_thickness / 2
        offset.Mode = 1
        offset.Join = 0
        offset.Fill = False
        document.recompute()
        if offset.Shape.isNull() or not offset.Shape.isValid():
            raise RuntimeError("FreeCAD could not create the arc offset wire.")
        outline = offset.Shape.Wires[0].copy()
        document.removeObject(offset.Name)
        document.removeObject(source.Name)
        result = _surface_filled_face(document, outline, points[0], flange_end,
                                      parameters.duct_thickness / 2)
    finally:
        App.closeDocument(document.Name)
    return result


def duct(parameters: DesignParameters):
    """Build the selected duct family as a planar FreeCAD face."""
    return _flanged_duct(parameters) if parameters.design_type == "flanged" else _airfoil_duct(parameters)
