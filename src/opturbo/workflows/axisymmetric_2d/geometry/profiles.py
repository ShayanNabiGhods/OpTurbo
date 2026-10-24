"""Builders for the independent x-r profiles."""

import math

import Part
from FreeCAD import Base

from .config import DesignParameters
from .freecad_helpers import checked
from .validation import actuator_outer_radius


def rectangle(parameters: DesignParameters):
    """Build the large 6750 by 9000 mm rectangle."""
    x0, r0 = parameters.domain_origin_x, parameters.domain_origin_r
    x1, r1 = x0 + parameters.domain_length, r0 + parameters.domain_height
    points = [Base.Vector(x0, r0, 0), Base.Vector(x0, r1, 0),
              Base.Vector(x1, r1, 0), Base.Vector(x1, r0, 0)]
    return checked(Part.Face(Part.makePolygon(points + [points[0]])),
                   "outer domain")


def resolution_section(parameters: DesignParameters):
    """Build a plain 1350 by 900 mm section with a tangent quarter arc."""
    x0, r0 = parameters.resolution_origin_x, parameters.resolution_origin_r
    radius = parameters.resolution_inlet_radius
    x1 = x0 + parameters.resolution_length
    bottom_left = Base.Vector(x0, r0, 0)
    curve_top = Base.Vector(x0 + radius, r0 + radius, 0)
    top_right = Base.Vector(x1, r0 + radius, 0)
    bottom_right = Base.Vector(x1, r0, 0)
    center = Base.Vector(x0 + radius, r0, 0)
    curve_mid = Base.Vector(center.x - radius / math.sqrt(2),
                            center.y + radius / math.sqrt(2), 0)
    edges = [
        Part.Arc(bottom_left, curve_mid, curve_top).toShape(),
        Part.LineSegment(curve_top, top_right).toShape(),
        Part.LineSegment(top_right, bottom_right).toShape(),
        Part.LineSegment(bottom_right, bottom_left).toShape(),
    ]
    return checked(Part.Face(Part.Wire(edges)), "resolution section")


def actuator_disk(parameters: DesignParameters):
    """Build the 405 by 5 mm annular actuator disk."""
    x = parameters.actuator_origin_x
    r0 = parameters.hub_origin_r + parameters.hub_radius
    r1 = parameters.hub_origin_r + actuator_outer_radius(parameters)
    half = parameters.actuator_thickness / 2
    points = [Base.Vector(x - half, r0, 0), Base.Vector(x - half, r1, 0),
              Base.Vector(x + half, r1, 0), Base.Vector(x + half, r0, 0)]
    return checked(Part.Face(Part.makePolygon(points + [points[0]])),
                   "actuator disk")


def hub(parameters: DesignParameters):
    """Build a hub with two rounded ends and a flat upper surface."""
    x0 = parameters.hub_origin_x - parameters.hub_length / 2
    x1 = parameters.hub_origin_x + parameters.hub_length / 2
    axis, radius = parameters.hub_origin_r, parameters.hub_radius
    left_tip, right_tip = Base.Vector(x0, axis, 0), Base.Vector(x1, axis, 0)
    left_top = Base.Vector(x0 + radius, axis + radius, 0)
    right_top = Base.Vector(x1 - radius, axis + radius, 0)
    left_mid = Base.Vector(x0 + radius - radius / math.sqrt(2),
                           axis + radius / math.sqrt(2), 0)
    right_mid = Base.Vector(x1 - radius + radius / math.sqrt(2),
                            axis + radius / math.sqrt(2), 0)
    edges = [
        Part.Arc(left_tip, left_mid, left_top).toShape(),
        Part.LineSegment(left_top, right_top).toShape(),
        Part.Arc(right_top, right_mid, right_tip).toShape(),
        Part.LineSegment(right_tip, left_tip).toShape(),
    ]
    return checked(Part.Face(Part.Wire(edges)), "hub")
