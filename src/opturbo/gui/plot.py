"""Small canvas-based result plots with no third-party dependencies."""

import math
import tkinter as tk


class LinePlot(tk.Canvas):
    """A lightweight line plot that needs no third-party package."""

    COLORS = ("#2f6fed", "#e05d44", "#1a9c68", "#9b59b6")

    def __init__(self, parent: tk.Misc, title: str, x_label: str, y_label: str,
                 log_ticks: bool = False, y_step: float | None = None,
                 smooth: bool = True, markers: bool = False, scatter: bool = False,
                 marker_size: int = 5, y_max: float | None = None, **kwargs):
        super().__init__(parent, background="white", highlightthickness=1,
                         highlightbackground="#c8ccd2", **kwargs)
        self.title, self.x_label, self.y_label = title, x_label, y_label
        self.log_ticks, self.y_step = log_ticks, y_step
        self.smooth, self.markers, self.scatter, self.marker_size = smooth, markers, scatter, marker_size
        self.y_max = y_max
        self.series: list[tuple[str, list[float]]] = []
        self.palette = {"canvas": "white", "text": "#20242a", "muted": "#606771", "grid": "#edf0f3", "axis": "#69717d"}
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_series(self, series: list[tuple[str, list[float]]]) -> None:
        self.series = series
        self.redraw()

    def set_palette(self, palette: dict[str, str]) -> None:
        """Apply the active application colours and redraw the chart."""
        self.palette = palette
        self.configure(background=palette["canvas"], highlightbackground=palette["axis"])
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 200), max(self.winfo_height(), 140)
        left, top, right, bottom = 70, 40, width - 18, height - 48
        self.create_text(12, 10, text=self.title, anchor="nw", font=("Segoe UI", 10, "bold"), fill=self.palette["text"])
        self.create_line(left, top, left, bottom, right, bottom, fill=self.palette["axis"])
        self.create_text((left + right) / 2, height - 8, text=self.x_label, fill=self.palette["muted"], font=("Segoe UI", 8))
        self.create_text(8, (top + bottom) / 2, text=self.y_label, angle=90, fill=self.palette["muted"], font=("Segoe UI", 8))
        values = [value for _, items in self.series for value in items if math.isfinite(value)]
        low, high = (min(values), max(values)) if values else ((-6, 0) if self.log_ticks else (0, 1))
        if self.y_max is not None:
            high = self.y_max
            if low >= high:
                low = min(0.0, high - 1.0)
        elif abs(high - low) < 1e-12:
            padding = self.y_step or 0.5
            low, high = low - padding, high + padding
        step = 1.0 if self.log_ticks else self.y_step or (high - low) / 4
        first, last = math.floor(low / step), math.ceil(high / step)
        low, high = first * step, last * step
        for tick in range(first, last + 1):
            value = tick * step
            y = bottom - (value - low) * (bottom - top) / (high - low)
            self.create_line(left, y, right, y, fill=self.palette["axis"], stipple="gray50")
            label = f"10^{tick}" if self.log_ticks else f"{value:.3g}"
            self.create_text(left - 6, y, text=label, anchor="e", fill=self.palette["muted"], font=("Segoe UI", 8))
            minor = ([value + math.log10(n) for n in range(2, 10)] if self.log_ticks
                     else [value + step * n / 5 for n in range(1, 5)])
            for position in minor:
                if low < position < high:
                    y_minor = bottom - (position - low) * (bottom - top) / (high - low)
                    self.create_line(left, y_minor, right, y_minor, fill=self.palette["grid"], dash=(2, 4))
        longest = max((len(items) for _, items in self.series), default=0)
        x_max = max(2, longest)
        x_step = max(1, math.ceil((x_max - 1) / 6))
        for index in range(1, x_max + 1):
            x = left + (index - 1) * (right - left) / (x_max - 1)
            major = (index - 1) % x_step == 0 or index == x_max
            self.create_line(x, top, x, bottom, fill=self.palette["axis"] if major else self.palette["grid"], dash=() if major else (2, 4))
            if major:
                self.create_text(x, bottom + 12, text=str(index), fill=self.palette["muted"], font=("Segoe UI", 8))
            if index < x_max and x_step == 1:
                middle = x + (right - left) / (x_max - 1) / 2
                self.create_line(middle, top, middle, bottom, fill=self.palette["grid"], dash=(2, 4))
        if not values:
            self.create_text(width / 2, height / 2, text="No results yet", fill=self.palette["muted"])
            return
        for series_index, (name, items) in enumerate(self.series):
            color = self.COLORS[series_index % len(self.COLORS)]
            coordinates: list[float] = []
            for index, value in enumerate(items):
                x = left + index * (right - left) / (x_max - 1)
                y = bottom - (value - low) * (bottom - top) / (high - low)
                coordinates.extend((x, y))
            if len(coordinates) >= 4 and not self.scatter:
                self.create_line(*coordinates, fill=color, width=2, smooth=self.smooth)
            if self.markers:
                radius = max(1, self.marker_size) / 2
                for point in range(0, len(coordinates), 2):
                    self.create_oval(coordinates[point] - radius, coordinates[point + 1] - radius,
                                     coordinates[point] + radius, coordinates[point + 1] + radius,
                                     fill=color, outline=color)
            elif len(coordinates) == 2:
                self.create_oval(coordinates[0] - 2, coordinates[1] - 2,
                                 coordinates[0] + 2, coordinates[1] + 2, fill=color)
            legend_x = right - 90 * (len(self.series) - series_index)
            if self.scatter:
                radius = max(1, self.marker_size) / 2
                self.create_oval(legend_x + 9 - radius, 17 - radius, legend_x + 9 + radius,
                                 17 + radius, fill=color, outline=color)
            else:
                self.create_line(legend_x, 17, legend_x + 18, 17, fill=color, width=3)
            self.create_text(legend_x + 23, 17, text=name, anchor="w", font=("Segoe UI", 8), fill=self.palette["text"])
