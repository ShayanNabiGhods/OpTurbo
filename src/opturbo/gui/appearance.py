"""Focused Tkinter behavior for the OpTurbo application."""

import re
import tkinter as tk
from tkinter import ttk

from ..models import AccessibilitySettings
from .widgets import ScrollableFrame


class AppearanceMixin:
    @staticmethod
    def _validate_numeric_entry(proposed: str) -> bool:
        """Limit editable numeric text to five fractional digits, including pasted text."""
        return re.fullmatch(r"[+-]?(?:(?:\d+(?:\.\d{0,5})?|\.\d{0,5})(?:[eE][+-]?\d*)?)?", proposed) is not None

    @staticmethod
    def _format_user_number(value: object) -> str:
        """Format displayed floating-point settings with at most five decimal places."""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return str(value)
        number = float(value)
        formatted = f"{number:.5f}".rstrip("0").rstrip(".")
        if formatted in {"", "-0", "+0", "0"} and number != 0.0:
            return f"{number:.5g}"
        return formatted or "0"

    @staticmethod
    def _theme_palette(settings: AccessibilitySettings) -> dict[str, str]:
        """Return accessible colours for the selected appearance settings."""
        if settings.high_contrast:
            return {"background": "#000000", "canvas": "#000000", "surface": "#111111", "text": "#ffffff",
                    "muted": "#e0e0e0", "accent": "#00d9ff", "grid": "#4a4a4a", "axis": "#ffffff"}
        if settings.theme == "dark":
            return {"background": "#1b1e23", "canvas": "#20242a", "surface": "#292e36", "text": "#eef2f7",
                    "muted": "#c0c8d2", "accent": settings.accent_color, "grid": "#3a424d", "axis": "#b8c1cc"}
        return {"background": "#f4f6f8", "canvas": "#ffffff", "surface": "#ffffff", "text": "#1d2a3a",
                "muted": "#59636f", "accent": settings.accent_color, "grid": "#edf0f3", "axis": "#69717d"}

    def _configure_style(self) -> None:
        """Apply the current visual scale and colour palette to ttk widgets."""
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        percent = int(self.text_scale_var.get()) if hasattr(self, "text_scale_var") else 100
        size = max(8, round(9 * percent / 100))
        colors = self.palette
        self.configure(background=colors["background"])
        style.configure("TFrame", background=colors["background"])
        style.configure("TLabel", background=colors["background"], foreground=colors["text"], font=("Segoe UI", size))
        style.configure("TLabelframe", background=colors["background"], foreground=colors["text"])
        style.configure("TLabelframe.Label", background=colors["background"], foreground=colors["text"], font=("Segoe UI", size, "bold"))
        style.configure("TButton", font=("Segoe UI", size), padding=(7, 4))
        style.configure("TEntry", fieldbackground=colors["surface"], foreground=colors["text"])
        style.configure("TCombobox", fieldbackground=colors["surface"], foreground=colors["text"],
                        arrowcolor=colors["text"])
        style.map(
            "TCombobox",
            fieldbackground=[("disabled", colors["surface"]), ("readonly", colors["surface"]),
                             ("!disabled", colors["surface"])],
            foreground=[("disabled", colors["muted"]), ("readonly", colors["text"]),
                        ("!disabled", colors["text"])],
            selectbackground=[("readonly", colors["surface"]), ("!disabled", colors["surface"])],
            selectforeground=[("readonly", colors["text"]), ("!disabled", colors["text"])],
        )
        row_spacing_var = getattr(self, "table_row_spacing_var", None)
        row_spacing = int(row_spacing_var.get()) if row_spacing_var else self.config_model.accessibility.table_row_spacing
        style.configure("Treeview", background=colors["surface"], fieldbackground=colors["surface"],
                        foreground=colors["text"], font=("Segoe UI", size),
                        rowheight=max(22, size + 12) + row_spacing)
        style.configure("Treeview.Heading", font=("Segoe UI", size, "bold"))
        style.configure("TScrollbar", background=colors["surface"], troughcolor=colors["background"],
                        arrowcolor=colors["muted"])
        style.map("TScrollbar", background=[("active", colors["accent"])])
        style.configure("Title.TLabel", font=("Segoe UI", max(14, size + 6), "bold"), foreground=colors["text"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", size), foreground=colors["muted"])
        style.configure("Accent.TButton", font=("Segoe UI", size, "bold"))
        style.configure("Accent.TButton", background=colors["accent"], foreground="white")
        style.map("TNotebook.Tab", background=[("selected", colors["accent"])], foreground=[("selected", "white")])
        style.configure("Horizontal.TProgressbar", background=colors["accent"])
        style.configure("Status.TLabel", padding=(8, 4), foreground=colors["muted"])
        self._refresh_native_theme_widgets()

    def _refresh_native_theme_widgets(self) -> None:
        """Apply theme colors to Tk widgets and native ttk combobox popdowns."""
        colors = self.palette

        def visit(widget: tk.Misc) -> None:
            if isinstance(widget, ScrollableFrame):
                widget.canvas.configure(background=colors["background"], highlightbackground=colors["background"])
            if isinstance(widget, ttk.Combobox):
                try:
                    popdown = str(self.tk.call("ttk::combobox::PopdownWindow", str(widget)))
                    listbox = f"{popdown}.f.l"
                    self.tk.call(
                        listbox, "configure",
                        "-background", colors["surface"],
                        "-foreground", colors["text"],
                        "-selectbackground", colors["accent"],
                        "-selectforeground", "white",
                    )
                except tk.TclError:
                    # Some Tcl/Tk builds create the native popdown only when first opened.
                    pass
            for child in widget.winfo_children():
                visit(child)

        visit(self)

    def _apply_accessibility(self, _event: object | None = None) -> None:
        """Apply appearance preferences immediately without restarting the app."""
        settings = AccessibilitySettings(theme=self.theme_var.get(), text_scale=int(self.text_scale_var.get()),
                                         high_contrast=self.high_contrast_var.get(), accent_color=self.accent_var.get(),
                                         candidate_marker_size=int(self.candidate_marker_size_var.get()),
                                         outer_marker_size=int(self.outer_marker_size_var.get()),
                                         table_row_spacing=int(self.table_row_spacing_var.get()))
        self.palette = self._theme_palette(settings)
        self.config_model.accessibility = settings
        self._configure_style()
        if hasattr(self, "mesh_study_controls") and self.mesh_study_controls:
            self._refresh_mesh_study_controls()
        for canvas in (getattr(self, "domain_canvas", None), getattr(self, "duct_canvas", None)):
            if canvas:
                canvas.configure(background=self.palette["canvas"])
        for plot in (getattr(self, name, None) for name in (
                "performance_plot", "bem_plot", "residual_plot", "outer_plot", "simple_bem_plot")):
            if plot:
                plot.set_palette({key: self.palette[key] for key in ("canvas", "text", "muted", "grid", "axis")})
        if getattr(self, "performance_plot", None):
            self.performance_plot.marker_size = settings.candidate_marker_size
            self.performance_plot.redraw()
        if getattr(self, "outer_plot", None):
            self.outer_plot.marker_size = settings.outer_marker_size
            self.outer_plot.redraw()
        if hasattr(self, "log_text"):
            self.log_text.configure(background=self.palette["canvas"], foreground=self.palette["text"],
                                    insertbackground=self.palette["text"])
        if hasattr(self, "mesh_study_details"):
            self.mesh_study_details.configure(
                background=self.palette["surface"], foreground=self.palette["text"],
                insertbackground=self.palette["text"], selectbackground=self.palette["accent"],
                selectforeground="white")
        self._draw_design()
