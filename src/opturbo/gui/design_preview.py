"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields, replace
import tkinter as tk
from tkinter import messagebox

from ..models import GeometrySettings, VariableSpec


class DesignPreviewMixin:
    def _update_preview_from_fields(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            self.config_model = self._read_model_from_fields()
            self._draw_design()
            self.status_var.set("Design preview updated")
        except Exception as error:
            messagebox.showerror("Invalid design", str(error))

    def _preview_values(self) -> tuple[GeometrySettings, list[VariableSpec]]:
        variables = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            try:
                variables.append(VariableSpec(spec.key, spec.label, float(value.get()),
                                              float(minimum.get()), float(maximum.get()), enabled.get()))
            except ValueError:
                return self.config_model.geometry, self.config_model.design_variables
        geometry = self.config_model.geometry
        try:
            geometry = GeometrySettings(**{
                item.name: (self.field_vars[("geometry", item.name)].get() if isinstance(getattr(geometry, item.name), bool)
                            else type(getattr(geometry, item.name))(self.field_vars[("geometry", item.name)].get()))
                for item in fields(GeometrySettings)
            })
        except (ValueError, tk.TclError):
            pass
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(geometry, **geometry_values)
        return geometry, variables

    def _draw_design(self) -> None:
        if not hasattr(self, "domain_canvas") or not self.parsec_rows:
            return
        geometry, variables = self._preview_values()
        try:
            top, bottom = self._duct_outline(geometry, variables)
        except Exception:
            return
        self._draw_domain(self.domain_canvas, geometry, top, bottom)
        self._draw_duct(self.duct_canvas, geometry, top, bottom)

    @staticmethod
    def _map_points(canvas: tk.Canvas, points: list[tuple[float, float]], bounds: tuple[float, float, float, float], margin: int = 35) -> list[float]:
        width, height = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 150)
        xmin, xmax, ymin, ymax = bounds
        scale = min((width - 2 * margin) / max(xmax - xmin, 1e-9), (height - 2 * margin) / max(ymax - ymin, 1e-9))
        offset_x = (width - scale * (xmax - xmin)) / 2
        offset_y = (height - scale * (ymax - ymin)) / 2
        mapped = []
        for x, y in points:
            mapped.extend((offset_x + (x - xmin) * scale, height - offset_y - (y - ymin) * scale))
        return mapped

    def _draw_axes(self, canvas: tk.Canvas, bounds: tuple[float, float, float, float]) -> None:
        """Draw labelled x/r axes, grid lines, and millimetre tick values."""
        xmin, xmax, ymin, ymax = bounds
        colors = self.palette
        for index in range(6):
            fraction = index / 5
            x = xmin + fraction * (xmax - xmin)
            y = ymin + fraction * (ymax - ymin)
            x0, y0 = self._map_points(canvas, [(x, ymin)], bounds)
            x1, y1 = self._map_points(canvas, [(xmin, y)], bounds)
            canvas.create_line(x0, 35, x0, max(canvas.winfo_height() - 35, 35), fill=colors["grid"])
            canvas.create_line(35, y1, max(canvas.winfo_width() - 35, 35), y1, fill=colors["grid"])
            canvas.create_text(x0, max(canvas.winfo_height() - 20, 20), text=f"{x:.0f}", fill=colors["muted"], font=("Segoe UI", 8))
            canvas.create_text(29, y1, text=f"{y:.0f}", anchor="e", fill=colors["muted"], font=("Segoe UI", 8))
        canvas.create_text(max(canvas.winfo_width() - 42, 42), max(canvas.winfo_height() - 8, 8), text="x (mm)", fill=colors["text"], font=("Segoe UI", 9, "bold"))
        canvas.create_text(10, 50, text="r (mm)", anchor="w", fill=colors["text"], font=("Segoe UI", 9, "bold"))
