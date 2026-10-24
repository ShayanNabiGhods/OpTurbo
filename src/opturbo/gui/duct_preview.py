"""Focused Tkinter behavior for the OpTurbo application."""

import math
import tkinter as tk

from ..models import GeometrySettings, VariableSpec
from ..workflows.axisymmetric_2d.geometry.parameters import (
    lower_profile,
    nested_parameters,
    profile,
)
from ..workflows.axisymmetric_2d.geometry.preview import (
    actuator_outline,
    hub_outline,
    outer_domain_outline,
    resolution_outline,
)


class DuctPreviewMixin:
    def _duct_points(self, geometry: GeometrySettings, x_values: list[float], upper: list[float], lower: list[float]) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        import math
        slope = math.tan(math.radians(geometry.duct_angle_deg))
        if geometry.duct_reverse:
            upper, lower = [-value for value in upper], [-value for value in lower]
        top, bottom = [], []
        for x, up, low in zip(x_values, upper, lower):
            axial = geometry.duct_origin_x + geometry.duct_chord * x
            center = geometry.duct_origin_r + geometry.duct_chord * x * slope
            top.append((axial, center + geometry.duct_chord * up))
            bottom.append((axial, center + geometry.duct_chord * low))
        return top, bottom

    def _flanged_duct_points(self, geometry: GeometrySettings, x_values: list[float], lower: list[float]) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """Mirror the FreeCAD five-term contour/flange construction for preview."""
        import math
        if geometry.duct_reverse:
            lower = [-value for value in lower]
        path = [(geometry.duct_origin_x + geometry.duct_chord * x,
                 geometry.duct_origin_r + geometry.duct_chord * y) for x, y in zip(x_values, lower)]
        angle = math.radians(geometry.duct_flange_angle_deg)
        end = (path[-1][0] + geometry.duct_flange_length * math.cos(angle),
               path[-1][1] + geometry.duct_flange_length * math.sin(angle))

        def normal(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
            dx, dy = second[0] - first[0], second[1] - first[1]
            length = math.hypot(dx, dy)
            return -dy / length, dx / length

        half = geometry.duct_thickness / 2
        left, right = [], []
        for index, point in enumerate(path):
            nx, ny = normal(path[max(0, index - 1)], path[min(len(path) - 1, index + 1)])
            left.append((point[0] + nx * half, point[1] + ny * half))
            right.append((point[0] - nx * half, point[1] - ny * half))
        nx, ny = normal(path[-2], path[-1])
        fx, fy = normal(path[-1], end)

        def intersect(point: tuple[float, float], direction: tuple[float, float], other: tuple[float, float], other_direction: tuple[float, float]) -> tuple[float, float]:
            cross = direction[0] * other_direction[1] - direction[1] * other_direction[0]
            if abs(cross) < 1e-12:
                raise ValueError("Contour and flange tangents must not be parallel.")
            dx, dy = other[0] - point[0], other[1] - point[1]
            scale = (dx * other_direction[1] - dy * other_direction[0]) / cross
            return point[0] + direction[0] * scale, point[1] + direction[1] * scale

        tail = path[-1]
        tangent = (tail[0] - path[-2][0], tail[1] - path[-2][1])
        flange_tangent = (end[0] - tail[0], end[1] - tail[1])
        left[-1] = intersect((tail[0] + nx * half, tail[1] + ny * half), tangent,
                             (tail[0] + fx * half, tail[1] + fy * half), flange_tangent)
        right[-1] = intersect((tail[0] - nx * half, tail[1] - ny * half), tangent,
                              (tail[0] - fx * half, tail[1] - fy * half), flange_tangent)
        return left + [(end[0] + fx * half, end[1] + fy * half)], right + [(end[0] - fx * half, end[1] - fy * half)]

    def _duct_outline(self, geometry: GeometrySettings, variables: list[VariableSpec]) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        parameters = nested_parameters(variables)
        if geometry.design_type == "flanged":
            x_values, lower = lower_profile(parameters, 140)
            return self._flanged_duct_points(geometry, x_values, lower)
        x_values, upper, lower = profile(parameters, 140)
        return self._duct_points(geometry, x_values, upper, lower)

    def _draw_domain(self, canvas: tk.Canvas, geometry: GeometrySettings, top: list[tuple[float, float]], bottom: list[tuple[float, float]]) -> None:
        canvas.delete("all")
        xmin, xmax = geometry.domain_origin_x, geometry.domain_origin_x + geometry.domain_length
        ymin, ymax = geometry.domain_origin_r, geometry.domain_origin_r + geometry.domain_height
        bounds = (xmin, xmax, ymin, ymax)
        self._draw_axes(canvas, bounds)
        domain = outer_domain_outline(geometry)
        canvas.create_polygon(*self._map_points(canvas, domain, bounds), fill=self.palette["surface"],
                              outline="#647386", width=2)
        region = resolution_outline(geometry)
        canvas.create_polygon(*self._map_points(canvas, region, bounds), fill="#dcecff",
                              outline="#4684bd", width=2)
        hub = hub_outline(geometry)
        canvas.create_polygon(*self._map_points(canvas, hub, bounds), fill="#7d8793",
                              outline="#35404c", width=2)
        disk = actuator_outline(geometry)
        canvas.create_polygon(*self._map_points(canvas, disk, bounds), fill="#1a9c68",
                              outline="#08724c", width=2)
        disk_center = [(geometry.actuator_origin_x, geometry.hub_origin_r + geometry.hub_radius),
                       (geometry.actuator_origin_x, geometry.hub_origin_r + geometry.hub_radius +
                        geometry.actuator_radial_span)]
        canvas.create_line(*self._map_points(canvas, disk_center, bounds), fill="#08724c", width=3)
        duct = top + list(reversed(bottom))
        canvas.create_polygon(*self._map_points(canvas, duct, bounds), fill="#efb1b5",
                              outline="#b52732", width=2)
        axis = [(xmin, geometry.domain_origin_r), (xmax, geometry.domain_origin_r)]
        canvas.create_line(*self._map_points(canvas, axis, bounds), fill="#20242a", width=2)
        canvas.create_text(14, 14, text="Axisymmetric domain preview (x–r, mm)", anchor="nw",
                           font=("Segoe UI", 10, "bold"), fill="#26313e")

    def _draw_context_inset(self, canvas: tk.Canvas, geometry: GeometrySettings,
                            top: list[tuple[float, float]], bottom: list[tuple[float, float]]) -> None:
        """Draw an overview inset so the zoomed duct remains connected to the turbine context."""
        width, height = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 150)
        left, upper, right, lower = width - 235, 18, width - 14, 155
        canvas.create_rectangle(left, upper, right, lower, fill=self.palette["surface"], outline=self.palette["axis"], width=1)
        bounds = (geometry.domain_origin_x, geometry.domain_origin_x + geometry.domain_length,
                  geometry.domain_origin_r, geometry.domain_origin_r + geometry.domain_height)

        def map_inset(points: list[tuple[float, float]]) -> list[float]:
            xmin, xmax, ymin, ymax = bounds
            scale = min((right - left - 12) / (xmax - xmin), (lower - upper - 24) / (ymax - ymin))
            offset_x = left + (right - left - scale * (xmax - xmin)) / 2
            offset_y = upper + 17 + (lower - upper - 20 - scale * (ymax - ymin)) / 2
            mapped = []
            for x, y in points:
                mapped.extend((offset_x + (x - xmin) * scale, lower - 7 - (y - ymin) * scale))
            return mapped

        canvas.create_polygon(*map_inset(resolution_outline(geometry)), fill="#dcecff", outline="#4684bd")
        canvas.create_polygon(*map_inset(hub_outline(geometry)), fill="#7d8793", outline="#35404c")
        canvas.create_polygon(*map_inset(actuator_outline(geometry)), fill="#1a9c68", outline="#08724c")
        canvas.create_polygon(*map_inset(top + list(reversed(bottom))), fill="#efb1b5", outline="#b52732")
        canvas.create_text(left + 6, upper + 6, text="Turbine context (x-r, mm)", anchor="nw", fill=self.palette["text"], font=("Segoe UI", 8, "bold"))

    def _draw_duct(self, canvas: tk.Canvas, geometry: GeometrySettings, top: list[tuple[float, float]], bottom: list[tuple[float, float]]) -> None:
        canvas.delete("all")
        points = top + bottom
        xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
        ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
        pad_x, pad_y = max((xmax - xmin) * 0.08, 1), max((ymax - ymin) * 0.25, 1)
        bounds = (xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y)
        self._draw_axes(canvas, bounds)
        # Use the duct's transform for the disk too: including the disk in the
        # fitted bounds would zoom out and hide the clearance we want to inspect.
        disk = self._map_points(canvas, actuator_outline(geometry), bounds)
        canvas.create_polygon(*disk, fill="#1a9c68", outline="#08724c", width=2,
                              tags="detail_actuator")
        canvas.create_text(42, 36, text="Green: actuator disk | Blue: duct", anchor="nw",
                           font=("Segoe UI", 9), fill=self.palette["text"])
        polygon = top + list(reversed(bottom))
        canvas.create_polygon(*self._map_points(canvas, polygon, bounds), fill="#dcecff", outline="#245f9e", width=2)
        self._draw_context_inset(canvas, geometry, top, bottom)
        canvas.create_text(42, 14, text=f"{geometry.design_type.title()} duct detail (x-r, mm)", anchor="nw", font=("Segoe UI", 10, "bold"), fill=self.palette["text"])
