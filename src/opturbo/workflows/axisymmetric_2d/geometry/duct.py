"""Builders for the airfoil and lower-PARSEC flanged duct profiles."""

import math

import Part
from FreeCAD import Base

from .config import DesignParameters
from .freecad_helpers import checked
from .parsec import coefficients, profile, surface
from .parameters import lower_profile


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
    points = list(edge.discretize(Number=max(3, min(4000, int(edge.Length / 0.25) + 3))))
    vertices = edge.Vertexes
    if len(vertices) >= 2:
        first, last = vertices[0].Point, vertices[-1].Point
        if points[0].sub(first).Length <= points[0].sub(last).Length:
            points[0], points[-1] = first, last
        else:
            points.reverse()
            points[0], points[-1] = last, first
    return points


def _join_edge_route(edges, indices, start_cap, end_cap):
    """Combine consecutive offset edges into one filling boundary curve."""
    remaining = [_edge_samples(edges[index]) for index in indices]
    if not remaining:
        raise RuntimeError("Offset boundary has an empty side between end caps.")
    cap_vertices = [vertex.Point for vertex in start_cap.Vertexes]
    first_edge = min(
        range(len(remaining)),
        key=lambda index: min(
            min(point.sub(vertex).Length for vertex in cap_vertices)
            for point in (remaining[index][0], remaining[index][-1])
        ),
    )
    points = remaining.pop(first_edge)
    if min(points[-1].sub(vertex).Length for vertex in cap_vertices) < min(
        points[0].sub(vertex).Length for vertex in cap_vertices
    ):
        points.reverse()
    current = points[-1]
    joined = points
    while remaining:
        matches = []
        for index, samples in enumerate(remaining):
            first_distance = samples[0].sub(current).Length
            last_distance = samples[-1].sub(current).Length
            distance = min(first_distance, last_distance)
            if distance <= 1e-5:
                matches.append((distance, index, last_distance < first_distance))
        if not matches:
            raise RuntimeError("Offset boundary edges are not connected at a shared endpoint.")
        _, index, reverse = min(matches)
        points = remaining.pop(index)
        if reverse:
            points.reverse()
        joined.extend(point for point in points[1:] if point.sub(joined[-1]).Length > 1e-7)
        current = joined[-1]
    end_vertices = [vertex.Point for vertex in end_cap.Vertexes]
    if min((current.sub(point).Length for point in end_vertices), default=1) > 1e-5:
        raise RuntimeError("Offset boundary does not meet its end cap.")
    curve = Part.BSplineCurve()
    curve.interpolate(joined)
    return curve.toShape()


def _boundary_routes(edges, start_index, end_index, tolerance=1e-5):
    """Trace both sides by shared endpoints instead of relying on edge order."""
    nodes = []

    def node_for(point):
        for index, known in enumerate(nodes):
            if point.sub(known).Length <= tolerance:
                return index
        nodes.append(point)
        return len(nodes) - 1

    endpoints = {}
    adjacency = {}
    for index, edge in enumerate(edges):
        if index in {start_index, end_index}:
            continue
        vertices = edge.Vertexes
        if len(vertices) < 2:
            raise RuntimeError("Offset boundary contains an edge without two endpoints.")
        first, last = node_for(vertices[0].Point), node_for(vertices[-1].Point)
        endpoints[index] = (first, last)
        adjacency.setdefault(first, []).append(index)
        adjacency.setdefault(last, []).append(index)

    start_nodes = {node_for(vertex.Point) for vertex in edges[start_index].Vertexes}

    def trace(origin):
        route, used, current = [], set(), origin
        for _ in range(len(endpoints)):
            if current in start_nodes:
                return route
            choices = [edge_index for edge_index in adjacency.get(current, ())
                       if edge_index not in used]
            if len(choices) != 1:
                raise RuntimeError("Offset boundary branches or has a gap between its caps.")
            edge_index = choices[0]
            used.add(edge_index)
            route.append(edge_index)
            first, last = endpoints[edge_index]
            current = last if current == first else first
        if current in start_nodes:
            return route
        raise RuntimeError("Offset boundary side does not reach its start cap.")

    routes = [trace(node_for(vertex.Point)) for vertex in edges[end_index].Vertexes]
    if len(routes) != 2 or routes[0] == routes[1]:
        raise RuntimeError("Offset boundary does not have two distinct sides.")
    return routes


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
    route_a, route_b = _boundary_routes(edges, start_index, end_index)
    side_a = _join_edge_route(edges, route_a, edges[end_index], edges[start_index])
    side_b = _join_edge_route(edges, list(reversed(route_b)), edges[start_index], edges[end_index])
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
