"""Exact 2D outlines shared by the GUI preview and geometry tests."""

from __future__ import annotations

import math

from .models import GeometrySettings


Point = tuple[float, float]


def outer_domain_outline(settings: GeometrySettings) -> list[Point]:
    """Return the closed rectangle exported as outer_domain.step."""
    x0, r0 = settings.domain_origin_x, settings.domain_origin_r
    x1, r1 = x0 + settings.domain_length, r0 + settings.domain_height
    return [(x0, r0), (x0, r1), (x1, r1), (x1, r0), (x0, r0)]


def resolution_outline(settings: GeometrySettings, arc_points: int = 25) -> list[Point]:
    """Return the quarter-circle inlet and straight edges from FreeCAD."""
    x0, r0 = settings.resolution_origin_x, settings.resolution_origin_r
    radius = settings.resolution_inlet_radius
    center_x = x0 + radius
    points = []
    for index in range(arc_points):
        fraction = index / (arc_points - 1)
        angle = math.pi - fraction * math.pi / 2
        points.append((center_x + radius * math.cos(angle), r0 + radius * math.sin(angle)))
    points[0] = (x0, r0)
    points[-1] = (center_x, r0 + radius)
    x1 = x0 + settings.resolution_length
    points.extend(((x1, r0 + radius), (x1, r0), (x0, r0)))
    return points


def actuator_outline(settings: GeometrySettings) -> list[Point]:
    """Return the finite-thickness annular actuator rectangle."""
    half = settings.actuator_thickness / 2
    x = settings.actuator_origin_x
    r0 = settings.hub_origin_r + settings.hub_radius
    r1 = r0 + settings.actuator_radial_span
    return [(x - half, r0), (x - half, r1), (x + half, r1),
            (x + half, r0), (x - half, r0)]


def hub_outline(settings: GeometrySettings, arc_points: int = 18) -> list[Point]:
    """Return the two rounded ends, flat top, and axis edge from FreeCAD."""
    x0 = settings.hub_origin_x - settings.hub_length / 2
    x1 = settings.hub_origin_x + settings.hub_length / 2
    axis, radius = settings.hub_origin_r, settings.hub_radius
    left_center, right_center = x0 + radius, x1 - radius
    points = []
    for index in range(arc_points):
        fraction = index / (arc_points - 1)
        angle = math.pi - fraction * math.pi / 2
        points.append((left_center + radius * math.cos(angle), axis + radius * math.sin(angle)))
    points.append((right_center, axis + radius))
    for index in range(1, arc_points):
        fraction = index / (arc_points - 1)
        angle = math.pi / 2 - fraction * math.pi / 2
        points.append((right_center + radius * math.cos(angle), axis + radius * math.sin(angle)))
    points.append((x0, axis))
    return points
