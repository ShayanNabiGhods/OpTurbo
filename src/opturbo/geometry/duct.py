"""Builders for the airfoil and lower-PARSEC flanged duct profiles."""

import math

import Part
from FreeCAD import Base

from .config import DesignParameters
from .freecad_helpers import checked
from .parsec import coefficients, profile, surface


PARSEC_DUCT = {
    "upper": {"leading_edge_radius": 0.0162187, "crest_location": 0.376723,
              "crest_height": 0.101977, "crest_curvature": -1.11136,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": -12.9184},
    "lower": {"leading_edge_radius": 0.00748922, "crest_location": 0.360,
              "crest_height": -0.11, "crest_curvature": 1.64354,
              "trailing_edge_height": 0.0, "trailing_edge_slope_deg": 0.148211},
}


def _line_intersection(first, first_direction, second, second_direction):
    cross = first_direction.x * second_direction.y - first_direction.y * second_direction.x
    if abs(cross) < 1e-12:
        raise ValueError("PARSEC and flange tangents must not be parallel.")
    delta_x, delta_y = second.x - first.x, second.y - first.y
    distance = (delta_x * second_direction.y - delta_y * second_direction.x) / cross
    return first + first_direction * distance


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
    """Build a lower PARSEC strip with an angled trailing flange as a face."""
    lower = parameters.parsec["lower"]
    x_values = [index / (parameters.duct_points - 1) for index in range(parameters.duct_points)]
    values = [surface(x, coefficients(lower, -1.0)) for x in x_values]
    if parameters.duct_reverse:
        values = [-value for value in values]
    bottom = [Base.Vector(parameters.duct_origin_x + parameters.duct_chord * x,
                          parameters.duct_origin_r + parameters.duct_chord * y, 0)
              for x, y in zip(x_values, values)]
    tail = bottom[-1]
    angle = math.radians(parameters.duct_flange_angle_deg)
    flange_end = Base.Vector(tail.x + parameters.duct_flange_length * math.cos(angle),
                             tail.y + parameters.duct_flange_length * math.sin(angle), 0)
    half_width = parameters.duct_thickness / 2
    left, right = [], []
    for index, point in enumerate(bottom):
        tangent = bottom[min(len(bottom) - 1, index + 1)].sub(bottom[max(0, index - 1)])
        tangent.normalize()
        normal = Base.Vector(-tangent.y, tangent.x, 0)
        left.append(point + normal * half_width)
        right.append(point - normal * half_width)
    lower_tangent = bottom[-1].sub(bottom[-2]); lower_tangent.normalize()
    flange_tangent = flange_end.sub(tail); flange_tangent.normalize()
    lower_normal = Base.Vector(-lower_tangent.y, lower_tangent.x, 0)
    flange_normal = Base.Vector(-flange_tangent.y, flange_tangent.x, 0)
    left_miter = _line_intersection(tail + lower_normal * half_width, lower_tangent,
                                    tail + flange_normal * half_width, flange_tangent)
    right_miter = _line_intersection(tail - lower_normal * half_width, lower_tangent,
                                     tail - flange_normal * half_width, flange_tangent)
    left[-1], right[-1] = left_miter, right_miter
    left_end = flange_end + flange_normal * half_width
    right_end = flange_end - flange_normal * half_width
    left_curve, right_curve = Part.BSplineCurve(), Part.BSplineCurve()
    left_curve.interpolate(left)
    right_curve.interpolate(list(reversed(right)))
    wire = Part.Wire([left_curve.toShape(), Part.LineSegment(left_miter, left_end).toShape(),
                      Part.LineSegment(left_end, right_end).toShape(),
                      Part.LineSegment(right_end, right_miter).toShape(), right_curve.toShape(),
                      Part.LineSegment(right[0], left[0]).toShape()])
    return checked(Part.Face(wire), "PARSEC flange face")


def duct(parameters: DesignParameters):
    """Build the selected duct family as a planar FreeCAD face."""
    return _flanged_duct(parameters) if parameters.design_type == "flanged" else _airfoil_duct(parameters)
