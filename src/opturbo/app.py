"""Tkinter desktop interface for configuring and running OpTurbo."""

from __future__ import annotations

from dataclasses import fields, replace
from copy import deepcopy
import json
import math
from pathlib import Path
import queue
import re
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable
import uuid

from .models import (
    AccessibilitySettings,
    CfdSettings,
    GaSettings,
    GeometrySettings,
    MeshSettings,
    ProjectConfig,
    ToolPaths,
    VariableSpec,
    default_design_variables,
)
from .optimizer import GeneticAlgorithm
from .objectives import OBJECTIVES, objective_value
from .parsec import lower_profile, nested_parameters, profile, validate_lower_profile, validate_profile
from .pipeline import PipelineRunner
from .pipeline.overlap import evaluate_generation
from .pipeline.failures import failed_candidate
from .preview import actuator_outline, hub_outline, outer_domain_outline, resolution_outline
from .storage import ProjectStore, atomic_json


APP_ROOT = Path(__file__).resolve().parents[2]


LABELS = {
    "freecad": "FreeCAD executable",
    "spaceclaim": "SpaceClaim executable",
    "workbench": "ANSYS Workbench executable",
    "fluent": "Fluent executable",
    "handoff_dir": "Fixed SpaceClaim handoff folder",
    "domain_length": "Domain length (mm)",
    "domain_height": "Domain height (mm)",
    "domain_origin_x": "Domain origin x (mm)",
    "domain_origin_r": "Domain origin r (mm)",
    "resolution_length": "Resolution-region length (mm)",
    "resolution_inlet_radius": "Resolution inlet radius (mm)",
    "resolution_origin_x": "Resolution origin x (mm)",
    "resolution_origin_r": "Resolution origin r (mm)",
    "actuator_radial_span": "Actuator radial span (mm)",
    "actuator_thickness": "Actuator thickness (mm)",
    "actuator_origin_x": "Actuator origin x (mm)",
    "hub_length": "Hub length (mm)",
    "hub_radius": "Hub radius (mm)",
    "hub_origin_x": "Hub origin x (mm)",
    "hub_origin_r": "Hub origin r (mm)",
    "duct_origin_x": "Duct origin x (mm)",
    "duct_origin_r": "Duct origin r (mm)",
    "design_type": "Duct design type",
    "duct_chord": "Duct chord (mm)",
    "duct_thickness": "Duct wall thickness (mm)",
    "duct_angle_deg": "Duct angle (deg)",
    "duct_flange_length": "Duct flange length (mm)",
    "duct_flange_angle_deg": "Duct flange angle (deg)",
    "duct_reverse": "Reverse duct profile",
    "duct_points": "Duct spline points",
    "global_size_cm": "Global element size (cm)",
    "growth_rate": "Growth rate",
    "cpu_cores": "CPU cores for parallel part meshing",
    "method": "Meshing method",
    "curvature_angle_deg": "Curvature angle (deg)",
    "resolution_size_cm": "Resolution-region size (cm)",
    "duct_size_cm": "Duct-wall size (cm)",
    "hub_size_cm": "Hub-wall size (cm)",
    "inflation_layers": "Inflation layers",
    "inflation_max_thickness_cm": "Inflation max thickness (cm)",
    "stations": "BEM radial stations",
    "flow_speed_m_s": "Free-stream speed (m/s)",
    "density_kg_m3": "Air density (kg/m³)",
    "viscosity_pa_s": "Dynamic viscosity (Pa·s)",
    "rotor_radius_m": "Rotor radius (m)",
    "hub_radius_m": "Rotor hub radius (m)",
    "blades": "Blade count",
    "omega_rad_s": "Rotor angular speed (rad/s)",
    "pitch_deg": "Blade pitch (deg)",
    "tip_loss_model": "Tip-loss correction",
    "bontempo_g_a": "Bontempo g coefficient A",
    "bontempo_g_b": "Bontempo g coefficient B",
    "bontempo_g_c": "Bontempo g coefficient C",
    "max_outer_iterations": "Maximum outer iterations",
    "fluent_iterations": "Fluent iterations per outer loop",
    "tolerance": "Cp/Ct convergence tolerance",
    "relaxation": "Source relaxation",
    "processors": "Fluent processor count",
    "keep_iteration_data": "Keep every outer-iteration solution data file",
    "viscous_model": "Viscous turbulence model",
    "residual_continuity": "Continuity residual criterion",
    "residual_x_velocity": "X-velocity residual criterion",
    "residual_y_velocity": "Y-velocity residual criterion",
    "residual_swirl": "Swirl residual criterion",
    "residual_k": "k residual criterion",
    "residual_epsilon": "Epsilon residual criterion",
    "residual_omega": "Omega residual criterion",
    "residual_nut": "Turbulent-viscosity residual criterion",
    "pressure_scheme": "Pressure discretization",
    "momentum_scheme": "Momentum discretization",
    "swirl_scheme": "Swirl discretization",
    "k_scheme": "k discretization",
    "epsilon_scheme": "Epsilon discretization",
    "omega_scheme": "Omega discretization",
    "nut_scheme": "Turbulent-viscosity discretization",
    "pressure_velocity_coupling": "Pressure-velocity coupling",
    "population_size": "Population size",
    "generations": "Generations",
    "elite_count": "Elite designs retained",
    "tournament_size": "Tournament size",
    "crossover_rate": "Crossover probability",
    "mutation_rate": "Mutation probability",
    "mutation_scale": "Mutation scale (fraction of range)",
    "random_seed": "Random seed",
    "objective": "Optimization criterion",
    "overlap_preparation": "Overlap meshing with Fluent (experimental)",
}


FIELD_HELP = {
    "overlap_preparation": "Prepare one next candidate through meshing while the current candidate runs Fluent. Same generation only. Stop waits for both active jobs; a prepared mesh is retained. Uses extra RAM and may require concurrent ANSYS licenses.",
    "objective": "Maximize Cp, Ct, or their flange-tip normalized values. Normalized values use the duct maximum radius, calculated from the selected candidate geometry.",
    "tip_loss_model": "prandtl: original tip and root factors. bontempo2025: duct-calibrated tip factor from page 5, Eq. (6), multiplied by the Prandtl root-loss factor.",
    "bontempo_g_a": "A in g = exp(A × (blade count × tip-speed ratio − B)) + C. Default: −0.229.",
    "bontempo_g_b": "Coefficient B in g = exp(A × (blade count × tip-speed ratio − B)) + C. Default: 22.0116.",
    "bontempo_g_c": "C in g = exp(A × (blade count × tip-speed ratio − B)) + C. Default: 0.4427.",
    "freecad": "Command-line FreeCAD executable used to create candidate STEP geometry.",
    "spaceclaim": "SpaceClaim executable used with the protected recorded import script.",
    "workbench": "ANSYS Workbench executable used to generate the mesh.",
    "fluent": "Fluent executable used for the CFD and BEM coupling run.",
    "handoff_dir": "Fixed folder required by the recorded SpaceClaim script; it cannot be changed here.",
    "domain_length": "Axial length of the outer CFD domain in millimetres.",
    "domain_height": "Radial height of the outer CFD domain in millimetres.",
    "domain_origin_x": "x-coordinate of the outer-domain inlet boundary in millimetres.",
    "domain_origin_r": "r-coordinate of the axisymmetric domain axis in millimetres.",
    "resolution_length": "Axial length of the locally refined mesh region in millimetres.",
    "resolution_inlet_radius": "Radius of the rounded inlet to the refined region in millimetres.",
    "resolution_origin_x": "x-coordinate where the refined region begins in millimetres.",
    "resolution_origin_r": "r-coordinate of the refined-region axis in millimetres.",
    "actuator_radial_span": "Blade-swept radial height represented by the actuator disk in millimetres.",
    "actuator_thickness": "Finite axial thickness of the actuator disk in millimetres.",
    "actuator_origin_x": "x-coordinate of the actuator-disk centre plane in millimetres.",
    "hub_length": "Axial hub length in millimetres.",
    "hub_radius": "Hub outer radius in millimetres.",
    "hub_origin_x": "x-coordinate of the hub centre in millimetres.",
    "hub_origin_r": "r-coordinate of the hub centre; normally the axis, 0 mm.",
    "duct_origin_x": "x-coordinate of the duct leading edge in millimetres.",
    "duct_origin_r": "r-coordinate of the duct leading edge in millimetres.",
    "duct_reverse": "Mirrors the duct contour about its reference line before geometry is created.",
    "duct_points": "Number of spline samples used to construct the duct; higher values make a smoother curve.",
    "global_size_cm": "Default mesh element size away from locally refined regions, in centimetres.",
    "growth_rate": "Controls the rate at which element sizes grow away from refined regions.",
    "cpu_cores": "Choose Program Controlled to use ANSYS Meshing's default, or select an explicit core count.",
    "method": "Default lets ANSYS choose the method automatically. Other choices add a method control to the whole-domain body.",
    "curvature_angle_deg": "Curvature angle used by the mesher to refine curved geometry.",
    "resolution_size_cm": "Target mesh size inside the resolution region, in centimetres.",
    "duct_size_cm": "Target mesh size along the duct wall, in centimetres.",
    "hub_size_cm": "Target mesh size along the hub wall, in centimetres.",
    "inflation_layers": "Number of boundary-layer mesh layers grown from walls.",
    "inflation_max_thickness_cm": "Maximum total boundary-layer thickness, in centimetres.",
    "flow_speed_m_s": "Free-stream inlet speed used by Fluent and BEM, in metres per second.",
    "density_kg_m3": "Air density used by the CFD and BEM models, in kilograms per cubic metre.",
    "viscosity_pa_s": "Dynamic air viscosity used by the CFD and BEM models, in pascal-seconds.",
    "rotor_radius_m": "Rotor tip radius used by the BEM model, in metres.",
    "hub_radius_m": "Rotor hub radius used by the BEM model, in metres.",
    "blades": "Number of rotor blades represented by the actuator-disk model.",
    "omega_rad_s": "Rotor angular speed used by BEM, in radians per second.",
    "pitch_deg": "Blade pitch angle used by BEM, in degrees.",
    "stations": "Number of radial BEM stations from hub to tip.",
    "max_outer_iterations": "Maximum Fluent/BEM coupling iterations for each candidate.",
    "fluent_iterations": "Fluent solver iterations performed during each coupling iteration.",
    "tolerance": "Cp/Ct change required to consider the coupled solution converged.",
    "relaxation": "Fraction of each new source-term update applied to Fluent, from 0 to 1.",
    "processors": "Number of Fluent processes to request for each CFD evaluation.",
    "keep_iteration_data": "Keep every intermediate Fluent data file instead of only the final result.",
    "viscous_model": "The first Fluent outer iteration selects k-omega standard, k-epsilon standard, or Spalart-Allmaras.",
    "residual_continuity": "Convergence limit for the continuity residual during the first Fluent setup.",
    "residual_x_velocity": "Convergence limit for the axial-velocity residual during the first Fluent setup.",
    "residual_y_velocity": "Convergence limit for the radial-velocity residual during the first Fluent setup.",
    "residual_swirl": "Convergence limit for the swirl-velocity residual during the first Fluent setup.",
    "residual_k": "Convergence limit used only with k-omega or k-epsilon.",
    "residual_epsilon": "Convergence limit used only with k-epsilon.",
    "residual_omega": "Convergence limit used only with k-omega.",
    "residual_nut": "Convergence limit used only with Spalart-Allmaras.",
    "pressure_scheme": "Pressure interpolation scheme selected during the first Fluent setup.",
    "momentum_scheme": "Momentum convection scheme selected during the first Fluent setup.",
    "swirl_scheme": "Swirl-velocity convection scheme selected during the first Fluent setup.",
    "k_scheme": "Turbulent kinetic-energy convection scheme used by k-omega or k-epsilon.",
    "epsilon_scheme": "Dissipation-rate convection scheme used only by k-epsilon.",
    "omega_scheme": "Specific-dissipation-rate convection scheme used only by k-omega.",
    "nut_scheme": "Turbulent-viscosity convection scheme used only by Spalart-Allmaras.",
    "pressure_velocity_coupling": "Pressure-velocity coupling method selected during the first Fluent setup.",
    "population_size": "Number of candidate designs evaluated in each GA generation.",
    "generations": "Number of GA generations to evaluate.",
    "elite_count": "Best candidates copied unchanged into the next generation.",
    "tournament_size": "Number of candidates compared when selecting each parent.",
    "crossover_rate": "Probability that each child combines values from both parents.",
    "mutation_rate": "Probability that each gene is randomly perturbed in a child.",
    "mutation_scale": "Standard deviation of a mutation as a fraction of that variable's range.",
    "random_seed": "Fixed seed that makes the optimization sequence reproducible.",
}


CFD_CHOICE_VALUES = {
    "viscous_model": ("k_omega", "k_epsilon", "spalart_allmaras"),
    "pressure_scheme": ("second_order", "standard", "presto", "linear",
                        "body_force_weighted"),
    "momentum_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                        "third_order_muscl"),
    "swirl_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                     "third_order_muscl"),
    "k_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                 "third_order_muscl"),
    "epsilon_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                       "third_order_muscl"),
    "omega_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                     "third_order_muscl"),
    "nut_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                   "third_order_muscl"),
    "pressure_velocity_coupling": ("simple", "simplec", "piso", "coupled"),
}

CPU_CORE_CHOICES = ("Program Controlled", *(str(value) for value in range(1, 129)))

TURBULENCE_EQUATIONS = {
    "k_omega": ("k", "omega"),
    "k_epsilon": ("k", "epsilon"),
    "spalart_allmaras": ("nut",),
}

TURBULENCE_FIELDS = {"viscous_model"} | {
    name for equation in ("k", "omega", "epsilon", "nut")
    for name in (f"residual_{equation}", f"{equation}_scheme")
}


class ToolTip:
    """Show a short explanation when the pointer rests over a GUI control."""

    def __init__(self, widget: tk.Misc, text: str):
        self.widget, self.text, self.window = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event: object = None) -> None:
        if self.window or not self.text:
            return
        x, y = self.widget.winfo_rootx() + 16, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        tk.Label(self.window, text=self.text, justify="left", wraplength=360,
                 background="#20242a", foreground="#f5f7fa", padx=8, pady=5).pack()

    def _hide(self, _event: object = None) -> None:
        if self.window:
            self.window.destroy()
            self.window = None


class ScrollableFrame(ttk.Frame):
    """A reusable vertically scrollable settings panel."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=8)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window, width=event.width))


class LinePlot(tk.Canvas):
    """A lightweight line plot that needs no third-party package."""

    COLORS = ("#2f6fed", "#e05d44", "#1a9c68", "#9b59b6")

    def __init__(self, parent: tk.Misc, title: str, x_label: str, y_label: str,
                 log_ticks: bool = False, y_step: float | None = None,
                 smooth: bool = True, markers: bool = False, scatter: bool = False,
                 marker_size: int = 5, **kwargs):
        super().__init__(parent, background="white", highlightthickness=1,
                         highlightbackground="#c8ccd2", **kwargs)
        self.title, self.x_label, self.y_label = title, x_label, y_label
        self.log_ticks, self.y_step = log_ticks, y_step
        self.smooth, self.markers, self.scatter, self.marker_size = smooth, markers, scatter, marker_size
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
        if abs(high - low) < 1e-12:
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


class OpTurboApp(tk.Tk):
    """Main application window and background-work coordinator."""

    def __init__(self):
        super().__init__()
        self.title("OpTurbo V0.0.1 — DAWT Optimization")
        self.geometry("1280x820")
        self.minsize(1050, 680)
        self.config_model = ProjectConfig()
        self.store: ProjectStore | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_requested = threading.Event()
        self.terminate_requested = threading.Event()
        self.residual_series: dict[str, list[float]] = {}
        self.residual_columns: list[str] = []
        self.outer_series: dict[str, list[float]] = {}
        self.worker: threading.Thread | None = None
        self.history: list[dict] = []
        self.history_lock = threading.Lock()
        self.best_fitness = float("-inf")
        self.field_vars: dict[tuple[str, str], tk.Variable] = {}
        self.bontempo_controls: list[ttk.Widget] = []
        self.parsec_rows: list[tuple[VariableSpec, tk.BooleanVar, tk.StringVar, tk.StringVar, tk.StringVar]] = []
        self.variable_controls: dict[str, tuple[ttk.Widget, ...]] = {}
        self.design_variable_sets: dict[str, list[VariableSpec]] = {}
        self.palette = self._theme_palette(AccessibilitySettings())
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._load_model_into_fields()
        self._update_resume_button()
        self.after(100, self._poll_events)

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
        style.configure("TCombobox", fieldbackground=colors["surface"], foreground=colors["text"])
        style.configure("Treeview", background=colors["surface"], fieldbackground=colors["surface"], foreground=colors["text"], font=("Segoe UI", size), rowheight=max(22, size + 12))
        style.configure("Treeview.Heading", font=("Segoe UI", size, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", max(14, size + 6), "bold"), foreground=colors["text"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", size), foreground=colors["muted"])
        style.configure("Accent.TButton", font=("Segoe UI", size, "bold"))
        style.configure("Accent.TButton", background=colors["accent"], foreground="white")
        style.map("TNotebook.Tab", background=[("selected", colors["accent"])], foreground=[("selected", "white")])
        style.configure("Horizontal.TProgressbar", background=colors["accent"])
        style.configure("Status.TLabel", padding=(8, 4), foreground=colors["muted"])

    def _apply_accessibility(self, _event: object | None = None) -> None:
        """Apply appearance preferences immediately without restarting the app."""
        settings = AccessibilitySettings(theme=self.theme_var.get(), text_scale=int(self.text_scale_var.get()),
                                         high_contrast=self.high_contrast_var.get(), accent_color=self.accent_var.get(),
                                         candidate_marker_size=int(self.candidate_marker_size_var.get()),
                                         outer_marker_size=int(self.outer_marker_size_var.get()))
        self.palette = self._theme_palette(settings)
        self.config_model.accessibility = settings
        self._configure_style()
        for canvas in (getattr(self, "domain_canvas", None), getattr(self, "duct_canvas", None)):
            if canvas:
                canvas.configure(background=self.palette["canvas"])
        for plot in (getattr(self, name, None) for name in ("performance_plot", "bem_plot", "residual_plot", "outer_plot")):
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
        self._draw_design()

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Project", command=self._new_project)
        file_menu.add_command(label="Open Project…", command=self._open_project)
        file_menu.add_command(label="Save Project", command=self._save_project)
        file_menu.add_command(label="Save Project As…", command=self._choose_project_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "About OpTurbo", "OpTurbo V0.0.1\nDAWT geometry-to-CFD genetic optimization"))
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="OpTurbo", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Geometry → SpaceClaim → Mesh → CFD/BEM → Genetic optimization",
                  style="Subtitle.TLabel").pack(side="left", padx=16, pady=(6, 0))
        self.status_var = tk.StringVar(value="Ready — choose a project folder to begin")
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="right")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._build_project_tab()
        self._build_design_tab()
        self._build_workflow_tab()
        self._build_optimization_tab()
        self._build_monitor_tab()
        self._build_accessibility_tab()

    def _build_project_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="  Project  ")
        tab.columnconfigure(0, weight=1, uniform="project_columns")
        tab.columnconfigure(1, weight=1, uniform="project_columns")
        tab.rowconfigure(0, weight=1)
        left = ttk.Frame(tab)
        right = ttk.Frame(tab)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        project_box = ttk.LabelFrame(left, text="Workflow project", padding=12)
        project_box.pack(fill="x")
        ttk.Label(project_box, text="Project name").grid(row=0, column=0, sticky="w", pady=5)
        self.project_name_var = tk.StringVar()
        ttk.Entry(project_box, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(project_box, text="Save folder").grid(row=1, column=0, sticky="w", pady=5)
        self.save_dir_var = tk.StringVar()
        ttk.Entry(project_box, textvariable=self.save_dir_var, state="readonly").grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(project_box, text="Choose…", command=self._choose_project_folder).grid(row=1, column=2)
        ttk.Button(project_box, text="Save now", command=self._save_project).grid(row=2, column=1, sticky="w", padx=8, pady=8)
        project_box.columnconfigure(1, weight=1)
        tools = ttk.LabelFrame(right, text="Installed engineering tools", padding=12)
        tools.pack(fill="both", expand=True)
        self._add_dataclass_form(tools, "tools", ToolPaths, browse_paths=True)
        note = ("SpaceClaim handoff is intentionally fixed at C:\\OpTurbo\\Temp Files. "
                "The application stages files there and copies all results into the selected workflow folder.")
        ttk.Label(left, text=note, style="Subtitle.TLabel", wraplength=480,
                  justify="left").pack(fill="x", pady=14)

    def _build_design_tab(self) -> None:
        tab = ttk.Panedwindow(self.notebook, orient="horizontal")
        self.notebook.add(tab, text="  Design  ")
        left = ttk.Frame(tab, padding=8)
        right = ttk.Frame(tab, padding=8)
        tab.add(left, weight=2)
        tab.add(right, weight=3)
        ttk.Label(left, text="Duct design", style="Title.TLabel").pack(anchor="w")
        chooser = ttk.Frame(left)
        chooser.pack(fill="x", pady=(4, 6))
        ttk.Label(chooser, text="Design type:").pack(side="left")
        self.design_type_var = tk.StringVar(value=self.config_model.geometry.design_type)
        design_picker = ttk.Combobox(chooser, textvariable=self.design_type_var, state="readonly",
                                     values=("airfoil", "flanged"), width=16)
        design_picker.pack(side="left", padx=8)
        design_picker.bind("<<ComboboxSelected>>", self._switch_design_type)
        ttk.Label(left, text="Only variables used by the selected design are shown. Unticked rows stay fixed.",
                  style="Subtitle.TLabel", wraplength=500).pack(anchor="w", pady=(0, 8))
        self.parsec_body = ttk.Frame(left)
        self.parsec_body.pack(fill="both", expand=True)
        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=8)
        ttk.Button(controls, text="Update preview", command=self._update_preview_from_fields).pack(side="left")
        ttk.Button(controls, text="Select all", command=lambda: self._select_parsec(True)).pack(side="left", padx=6)
        ttk.Button(controls, text="Clear all", command=lambda: self._select_parsec(False)).pack(side="left")
        views = ttk.Notebook(right)
        views.pack(fill="both", expand=True)
        whole = ttk.Frame(views)
        zoom = ttk.Frame(views)
        views.add(whole, text="Whole domain")
        views.add(zoom, text="Duct detail")
        self.domain_canvas = tk.Canvas(whole, background="white", highlightthickness=0)
        self.duct_canvas = tk.Canvas(zoom, background="white", highlightthickness=0)
        self.domain_canvas.pack(fill="both", expand=True)
        self.duct_canvas.pack(fill="both", expand=True)
        self.domain_canvas.bind("<Configure>", lambda _event: self._draw_design())
        self.duct_canvas.bind("<Configure>", lambda _event: self._draw_design())

    def _build_workflow_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="  Workflow Settings  ")
        pages = ttk.Notebook(tab)
        pages.pack(fill="both", expand=True)
        for title, section, cls in (("Geometry", "geometry", GeometrySettings),
                                    ("Meshing", "mesh", MeshSettings),
                                    ("CFD / BEM", "cfd", CfdSettings)):
            if section == "cfd":
                page = ScrollableFrame(pages)
                body = page.body
            else:
                page = ttk.Frame(pages, padding=8)
                body = page
            pages.add(page, text=title)
            # Initialize a persistent variable for every setting before placing
            # fields into separate groups (including currently hidden equations).
            self._add_dataclass_form(body, section, cls,
                                     exclude={item.name for item in fields(cls)})
            if section == "geometry":
                groups = (
                    ("Outer domain", ("domain_length", "domain_height", "domain_origin_x", "domain_origin_r")),
                    ("Resolution region", ("resolution_length", "resolution_inlet_radius", "resolution_origin_x", "resolution_origin_r")),
                    ("Actuator disk", ("actuator_radial_span", "actuator_thickness", "actuator_origin_x")),
                    ("Hub and duct placement", ("hub_length", "hub_radius", "hub_origin_x", "hub_origin_r", "duct_origin_x", "duct_origin_r", "duct_points")),
                )
                self._place_setting_groups(body, section, cls, groups, exclude={
                    "design_type", "duct_angle_deg", "duct_chord", "duct_thickness",
                    "duct_flange_length", "duct_flange_angle_deg"})
            elif section == "mesh":
                groups = (
                    ("Global mesh controls", ("global_size_cm", "growth_rate", "cpu_cores", "method", "curvature_angle_deg")),
                    ("Local sizing", ("resolution_size_cm", "duct_size_cm", "hub_size_cm")),
                    ("Inflation layers", ("inflation_layers", "inflation_max_thickness_cm")),
                )
                self._place_setting_groups(body, section, cls, groups)
            else:
                groups = (
                    ("Flow and rotor", ("flow_speed_m_s", "density_kg_m3", "viscosity_pa_s", "rotor_radius_m", "hub_radius_m", "blades", "omega_rad_s", "pitch_deg")),
                    ("BEM correction", ("stations", "tip_loss_model")),
                    ("Fluent / BEM coupling", ("max_outer_iterations", "fluent_iterations", "tolerance", "relaxation", "processors", "keep_iteration_data")),
                    ("Fluent discretization", ("pressure_scheme", "momentum_scheme", "swirl_scheme", "pressure_velocity_coupling")),
                    ("General residual criteria", ("residual_continuity", "residual_x_velocity", "residual_y_velocity", "residual_swirl")),
                )
                columns = self._place_setting_groups(body, section, cls, groups)
                self.turbulence_panel = ttk.LabelFrame(
                    columns[1], text="Turbulence model and equation residuals", padding=10)
                self.turbulence_panel.pack(fill="x", padx=7, pady=6)
                self.field_vars[("cfd", "viscous_model")].trace_add("write", self._refresh_turbulence_controls)
                self._refresh_turbulence_controls()
                self.bontempo_panel = ttk.LabelFrame(
                    columns[1], text="Bontempo g coefficients", padding=8)
                self.bontempo_panel.pack(fill="x", padx=7, pady=6)
                self._add_dataclass_form(self.bontempo_panel, section, cls,
                                         include={"bontempo_g_a", "bontempo_g_b", "bontempo_g_c"},
                                         inline_help=False)
                self.field_vars[("cfd", "tip_loss_model")].trace_add("write", self._refresh_bontempo_controls)
                self._refresh_bontempo_controls()

    def _place_setting_groups(self, parent: ttk.Frame, section: str, cls: type,
                              groups: tuple[tuple[str, tuple[str, ...]], ...],
                              exclude: set[str] | None = None) -> tuple[ttk.Frame, ttk.Frame]:
        """Stack related settings groups in two independent compact columns."""
        columns = (ttk.Frame(parent), ttk.Frame(parent))
        for column, frame in enumerate(columns):
            frame.grid(row=0, column=column, sticky="new")
            parent.columnconfigure(column, weight=1, uniform=f"{section}_groups")
        for index, (title, names) in enumerate(groups):
            group = ttk.LabelFrame(columns[index % 2], text=title, padding=8)
            group.pack(fill="x", padx=7, pady=6)
            self._add_dataclass_form(group, section, cls, exclude=exclude,
                                     include=set(names), inline_help=False)
        return columns

    def _refresh_turbulence_controls(self, *_args: object) -> None:
        """Show active-model equations while retaining values for hidden models."""
        panel = self.turbulence_panel
        for child in panel.winfo_children():
            child.destroy()
        ttk.Label(panel, text="Viscous turbulence model").grid(row=0, column=0, sticky="w", padx=5)
        model = self.field_vars[("cfd", "viscous_model")]
        ttk.Combobox(panel, textvariable=model, values=CFD_CHOICE_VALUES["viscous_model"],
                     state="readonly", width=24).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(panel, text="Only active equations are shown. Switching models preserves your settings.",
                  style="Subtitle.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        for column, equation in enumerate(TURBULENCE_EQUATIONS.get(model.get(), ())):
            group = ttk.LabelFrame(panel, text=equation, padding=8)
            group.grid(row=2, column=column, sticky="new", padx=5)
            for row, name in enumerate((f"residual_{equation}", f"{equation}_scheme")):
                ttk.Label(group, text=LABELS[name]).grid(row=row * 3, column=0, sticky="w")
                variable = self.field_vars[("cfd", name)]
                if name in CFD_CHOICE_VALUES:
                    control = ttk.Combobox(group, textvariable=variable, values=CFD_CHOICE_VALUES[name],
                                            state="readonly", width=24)
                else:
                    control = ttk.Entry(group, textvariable=variable, width=24)
                control.grid(row=row * 3 + 1, column=0, sticky="w", pady=3)
                ttk.Label(group, text=FIELD_HELP[name], style="Subtitle.TLabel", wraplength=330,
                          justify="left").grid(row=row * 3 + 2, column=0, sticky="w", pady=(0, 8))
                ToolTip(control, FIELD_HELP[name])
        for column in (0, 1):
            panel.columnconfigure(column, weight=1, uniform="turbulence")

    def _refresh_bontempo_controls(self, *_args: object) -> None:
        """Gray empirical g coefficients unless the Bontempo correction is selected."""
        enabled = self.field_vars[("cfd", "tip_loss_model")].get() == "bontempo2025"
        for control in self.bontempo_controls:
            control.configure(state="normal" if enabled else "disabled")

    def _build_optimization_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="  Optimization  ")
        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        settings = ttk.Frame(pane, padding=8)
        results = ttk.Frame(pane, padding=(12, 0))
        pane.add(settings, weight=1)
        pane.add(results, weight=2)
        self._add_dataclass_form(settings, "ga", GaSettings)
        actions = ttk.Frame(settings)
        actions.grid(row=50, column=0, columnspan=3, sticky="ew", pady=16)
        self.single_button = ttk.Button(actions, text="Evaluate current design", command=self._run_single)
        self.single_button.pack(fill="x", pady=3)
        self.start_button = ttk.Button(actions, text="Start GA optimization", style="Accent.TButton", command=self._run_ga)
        self.start_button.pack(fill="x", pady=3)
        self.resume_button = ttk.Button(actions, text="Resume previous optimization", command=self._resume_ga,
                                        state="disabled")
        self.resume_button.pack(fill="x", pady=3)
        self.stop_button = ttk.Button(actions, text="Stop after current candidate", command=self._stop, state="disabled")
        self.stop_button.pack(fill="x", pady=3)
        self.terminate_button = ttk.Button(actions, text="Terminate whole process", command=self._terminate, state="disabled")
        self.terminate_button.pack(fill="x", pady=3)
        ttk.Label(results, text="Optimization progress", style="Title.TLabel").pack(anchor="w")
        self.progress = ttk.Progressbar(results, mode="determinate")
        self.progress.pack(fill="x", pady=8)
        columns = ("evaluation", "generation", "candidate", "cp", "ct", "status")
        self.results_tree = ttk.Treeview(results, columns=columns, show="headings", height=16)
        widths = (80, 80, 80, 105, 105, 180)
        for name, width in zip(columns, widths):
            self.results_tree.heading(name, text=name.replace("_", " ").title())
            self.results_tree.column(name, width=width, anchor="center")
        self.results_tree.pack(fill="both", expand=True)
        self.best_var = tk.StringVar(
            value=f"Best {OBJECTIVES.get(self.config_model.ga.objective, 'objective')}: —")
        ttk.Label(results, textvariable=self.best_var, style="Title.TLabel").pack(anchor="w", pady=10)

    def _build_monitor_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  Monitor  ")
        tab.columnconfigure(0, weight=1, uniform="monitor_columns")
        tab.columnconfigure(1, weight=1, uniform="monitor_columns")
        tab.rowconfigure(0, weight=1, uniform="monitor_rows")
        tab.rowconfigure(1, weight=1, uniform="monitor_rows")
        log_frame = ttk.LabelFrame(tab, text="Fluent and pipeline log", padding=5)
        plots = ttk.Notebook(tab)
        plots.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 0))
        performance = ttk.Frame(plots)
        bem = ttk.Frame(plots)
        residual = ttk.Frame(plots)
        outer = ttk.Frame(plots)
        for frame, title in ((performance, "Candidates"), (bem, "BEM"), (residual, "Live residuals"), (outer, "Outer Cp / Ct")):
            plots.add(frame, text=title)
        log_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
        self.log_text = tk.Text(log_frame, wrap="none", background="#121820", foreground="#dce5ef",
                                insertbackground="white", font=("Consolas", 9), state="disabled")
        yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        xscroll = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.performance_plot = LinePlot(performance, "Optimization objective history", "Evaluation (-)", "Cp / Ct (-)",
                                         markers=True, scatter=True, height=260)
        self.performance_plot.pack(fill="both", expand=True)
        self.bem_plot = LinePlot(bem, "Latest radial BEM solution", "Radial station (-)", "Value (-)", height=260)
        self.bem_plot.pack(fill="both", expand=True)
        self.residual_plot = LinePlot(residual, "Current Fluent run", "Solver iteration sample (-)", "Residual (-)", log_ticks=True)
        self.residual_plot.pack(fill="both", expand=True)
        self.outer_plot = LinePlot(outer, "Current candidate coupling", "Outer iteration (-)", "Cp / Ct (-)",
                                   y_step=0.1, markers=True, smooth=False)
        self.outer_plot.pack(fill="both", expand=True)

    def _build_accessibility_tab(self) -> None:
        """Build visual and keyboard-use settings that are safe to change at runtime."""
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="  Accessibility  ")
        panel = ttk.LabelFrame(tab, text="Display and interaction", padding=14)
        panel.pack(anchor="nw", fill="x")
        ttk.Label(panel, text="Appearance", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Choose a colour theme, enlarge text, or enable high contrast. Changes apply immediately and are saved with the project.",
                  style="Subtitle.TLabel", wraplength=680, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        self.theme_var = tk.StringVar(value="light")
        self.text_scale_var = tk.StringVar(value="100")
        self.high_contrast_var = tk.BooleanVar(value=False)
        self.accent_var = tk.StringVar(value="#2f6fed")
        self.candidate_marker_size_var = tk.StringVar(value="5")
        self.outer_marker_size_var = tk.StringVar(value="5")
        ttk.Label(panel, text="Theme").grid(row=2, column=0, sticky="w", pady=5)
        theme = ttk.Combobox(panel, textvariable=self.theme_var, values=("light", "dark"), state="readonly", width=14)
        theme.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Label(panel, text="Light uses the default palette; dark reduces screen brightness.", style="Subtitle.TLabel", wraplength=420).grid(row=3, column=1, sticky="w")
        ttk.Label(panel, text="Text size").grid(row=4, column=0, sticky="w", pady=(12, 5))
        text_scale = ttk.Combobox(panel, textvariable=self.text_scale_var, values=("90", "100", "110", "125", "150", "175", "200"), state="readonly", width=14)
        text_scale.grid(row=4, column=1, sticky="w", pady=(12, 5))
        ttk.Label(panel, text="Scales interface text from 90% to 150%.", style="Subtitle.TLabel").grid(row=5, column=1, sticky="w")
        contrast = ttk.Checkbutton(panel, text="High contrast", variable=self.high_contrast_var, command=self._apply_accessibility)
        contrast.grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 2))
        ttk.Label(panel, text="Uses a black background, white text, and a bright focus colour for maximum contrast.",
                  style="Subtitle.TLabel", wraplength=520).grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Keyboard use", style="Title.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(22, 0))
        ttk.Label(panel, text="Use Tab and Shift+Tab to move between controls, Space to toggle checkboxes, and Enter to activate a focused button. Hover any control for a short explanation.",
                  style="Subtitle.TLabel", wraplength=680, justify="left").grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        theme.bind("<<ComboboxSelected>>", self._apply_accessibility)
        text_scale.bind("<<ComboboxSelected>>", self._apply_accessibility)
        ToolTip(theme, "Switch between light and dark appearance.")
        ToolTip(text_scale, "Change the size of text throughout the application.")
        ToolTip(contrast, "Increase colour contrast for easier reading.")
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Accent color (blue / teal / purple / orange)").grid(row=10, column=0, sticky="w", pady=12)
        accent = ttk.Combobox(panel, textvariable=self.accent_var, values=("#2f6fed", "#007d79", "#7540a8", "#a74700"), state="readonly", width=14)
        accent.grid(row=10, column=1, sticky="w")
        accent.bind("<<ComboboxSelected>>", self._apply_accessibility)
        ttk.Label(panel, text="Accent highlights selected tabs, primary actions and progress. High contrast overrides it.", style="Subtitle.TLabel").grid(row=11, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Candidate marker size").grid(row=12, column=0, sticky="w", pady=(12, 5))
        candidate_markers = ttk.Combobox(panel, textvariable=self.candidate_marker_size_var,
                                         values=tuple(str(size) for size in range(2, 13)), state="readonly", width=14)
        candidate_markers.grid(row=12, column=1, sticky="w", pady=(12, 5))
        ttk.Label(panel, text="Marker size for candidate results in the Candidates panel.", style="Subtitle.TLabel").grid(row=13, column=1, sticky="w")
        ttk.Label(panel, text="Outer Cp / Ct marker size").grid(row=14, column=0, sticky="w", pady=(8, 5))
        outer_markers = ttk.Combobox(panel, textvariable=self.outer_marker_size_var,
                                     values=tuple(str(size) for size in range(2, 13)), state="readonly", width=14)
        outer_markers.grid(row=14, column=1, sticky="w", pady=(8, 5))
        ttk.Label(panel, text="Marker size for the Outer Cp / Ct panel.", style="Subtitle.TLabel").grid(row=15, column=1, sticky="w")
        candidate_markers.bind("<<ComboboxSelected>>", self._apply_accessibility)
        outer_markers.bind("<<ComboboxSelected>>", self._apply_accessibility)

    def _add_dataclass_form(self, parent: ttk.Frame, section: str, cls: type,
                            browse_paths: bool = False, exclude: set[str] | None = None,
                            two_columns: bool = False,
                            include: set[str] | None = None,
                            inline_help: bool = True) -> None:
        """Create labeled entries for every field in a settings dataclass."""
        row = 0
        container = parent
        all_fields = list(fields(cls))
        for index, item in enumerate(all_fields):
            if two_columns and index in (0, (len(all_fields) + 1) // 2):
                column = 0 if index == 0 else 1
                parent = ttk.Frame(container, padding=8)
                parent.grid(row=0, column=column, sticky="new")
                container.columnconfigure(column, weight=1, uniform="settings")
                row = 0
            key = (section, item.name)
            label = LABELS.get(item.name, item.name.replace("_", " ").title())
            default = getattr(cls(), item.name)
            variable = self.field_vars.get(key)
            if variable is None:
                variable = tk.BooleanVar() if isinstance(default, bool) else tk.StringVar()
                self.field_vars[key] = variable
            if exclude and item.name in exclude:
                continue
            if include is not None and item.name not in include:
                continue
            if section == "cfd" and item.name == "tip_loss_model":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=("prandtl", "bontempo2025"))
            elif section == "ga" and item.name == "objective":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=tuple(OBJECTIVES))
            elif section == "cfd" and item.name in CFD_CHOICE_VALUES:
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=CFD_CHOICE_VALUES[item.name])
            elif section == "mesh" and item.name == "method":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=("Default (ANSYS automatic)", "Quad", "Tri", "MultiZone"))
            elif section == "mesh" and item.name == "cpu_cores":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=CPU_CORE_CHOICES)
            elif isinstance(default, bool):
                widget = ttk.Checkbutton(parent, variable=variable)
            else:
                widget = ttk.Entry(parent, textvariable=variable, width=24)
            if section == "cfd" and item.name in {"bontempo_g_a", "bontempo_g_b", "bontempo_g_c"}:
                self.bontempo_controls.append(widget)
            label_widget = ttk.Label(parent, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=5, pady=5)
            widget.grid(row=row, column=1, sticky="ew" if browse_paths else "w", padx=5, pady=5)
            help_text = FIELD_HELP.get(item.name, f"Controls {label.lower()}.")
            if inline_help:
                ttk.Label(parent, text=help_text, style="Subtitle.TLabel", wraplength=360,
                          justify="left").grid(row=row + 1, column=1, columnspan=2,
                                               sticky="w", padx=5, pady=(0, 5))
            ToolTip(label_widget, help_text)
            ToolTip(widget, help_text)
            if section == "tools" and item.name == "handoff_dir":
                widget.configure(state="readonly")
                ttk.Label(parent, text="Protected", foreground="#a34a2a").grid(row=row, column=2, padx=4)
            elif browse_paths:
                ttk.Button(parent, text="Browse…", command=lambda var=variable: self._browse_tool(var)).grid(row=row, column=2, padx=4)
            row += 2 if inline_help else 1
        parent.columnconfigure(1, weight=1)

    def _make_parsec_rows(self) -> None:
        for child in self.parsec_body.winfo_children():
            child.destroy()
        self.parsec_rows.clear()
        self.variable_controls.clear()
        for column, text in ((0, "Use"), (1, "Parameter"), (2, "Minimum"), (3, "Value"), (4, "Maximum")):
            ttk.Label(self.parsec_body, text=text).grid(row=0, column=column, sticky="w", padx=3)
        for row, spec in enumerate(self.config_model.design_variables, start=1):
            enabled = tk.BooleanVar(value=spec.optimize)
            value = tk.StringVar(value=str(spec.value))
            minimum = tk.StringVar(value=str(spec.minimum))
            maximum = tk.StringVar(value=str(spec.maximum))
            use = ttk.Checkbutton(self.parsec_body, variable=enabled)
            use.grid(row=row, column=0, padx=3, pady=3)
            label = ttk.Label(self.parsec_body, text=spec.label)
            value_entry = ttk.Entry(self.parsec_body, textvariable=value, width=11)
            minimum_entry = ttk.Entry(self.parsec_body, textvariable=minimum, width=11)
            maximum_entry = ttk.Entry(self.parsec_body, textvariable=maximum, width=11)
            label.grid(row=row, column=1, sticky="w", padx=3)
            minimum_entry.grid(row=row, column=2, padx=3)
            value_entry.grid(row=row, column=3, padx=3)
            maximum_entry.grid(row=row, column=4, padx=3)
            hint = f"Select to optimize {spec.label.lower()}; otherwise its current value stays fixed."
            ToolTip(use, hint)
            ToolTip(label, hint)
            ToolTip(value_entry, f"Current design value for {spec.label.lower()}.")
            ToolTip(minimum_entry, f"Lowest permitted optimization value for {spec.label.lower()}.")
            ToolTip(maximum_entry, f"Highest permitted optimization value for {spec.label.lower()}.")
            value.trace_add("write", lambda *_args: self.after_idle(self._draw_design))
            self.parsec_rows.append((spec, enabled, value, minimum, maximum))
            self.variable_controls[spec.key] = (label, value_entry, minimum_entry, maximum_entry)
            enabled.trace_add("write", lambda *_args, key=spec.key, flag=enabled:
                              self._set_variable_row_state(key, flag.get()))
            self._set_variable_row_state(spec.key, enabled.get())
        self.parsec_body.columnconfigure(1, weight=1)
        for column in (0, 2, 3, 4):
            self.parsec_body.columnconfigure(column, weight=0)

    def _set_variable_row_state(self, key: str, enabled: bool) -> None:
        """Gray and lock fixed design-variable rows while keeping their checkbox usable."""
        state = "!disabled" if enabled else "disabled"
        for widget in self.variable_controls.get(key, ()):
            widget.state([state])

    def _load_model_into_fields(self) -> None:
        self.project_name_var.set(self.config_model.project_name)
        self.save_dir_var.set(self.config_model.save_dir)
        for section in ("tools", "geometry", "mesh", "cfd", "ga"):
            settings = getattr(self.config_model, section)
            for item in fields(settings):
                variable = self.field_vars[(section, item.name)]
                value = getattr(settings, item.name)
                if section == "mesh" and item.name == "cpu_cores":
                    value = "Program Controlled" if value is None else str(value)
                elif section == "mesh" and item.name == "method" and value == "Default":
                    value = "Default (ANSYS automatic)"
                variable.set(value)
        self.design_type_var.set(self.config_model.geometry.design_type)
        self.theme_var.set(self.config_model.accessibility.theme)
        self.text_scale_var.set(str(self.config_model.accessibility.text_scale))
        self.high_contrast_var.set(self.config_model.accessibility.high_contrast)
        self.accent_var.set(self.config_model.accessibility.accent_color)
        self.candidate_marker_size_var.set(str(self.config_model.accessibility.candidate_marker_size))
        self.outer_marker_size_var.set(str(self.config_model.accessibility.outer_marker_size))
        if hasattr(self, "best_var"):
            self.best_var.set(f"Best {OBJECTIVES.get(self.config_model.ga.objective, 'objective')}: —")
        self.design_variable_sets = {self.config_model.geometry.design_type: self.config_model.design_variables[:]}
        self._make_parsec_rows()
        self._apply_accessibility()
        self._draw_design()

    def _switch_design_type(self, _event: object | None = None) -> None:
        """Replace the Design-tab choices with those valid for the selected duct."""
        if self.worker and self.worker.is_alive():
            self.design_type_var.set(self.config_model.geometry.design_type)
            return
        selected = self.design_type_var.get()
        current = self.config_model.geometry.design_type
        if selected == current or selected not in {"airfoil", "flanged"}:
            return
        current_rows = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            try:
                current_rows.append(VariableSpec(spec.key, spec.label, float(value.get()),
                                                 float(minimum.get()), float(maximum.get()), enabled.get()))
            except ValueError:
                current_rows.append(spec)
        self.design_variable_sets[current] = current_rows
        next_rows = self.design_variable_sets.get(selected, default_design_variables(selected))
        self.config_model.geometry = replace(self.config_model.geometry, design_type=selected,
                                             duct_reverse=(selected == "airfoil"))
        self.field_vars[("geometry", "design_type")].set(selected)
        self.field_vars[("geometry", "duct_reverse")].set(selected == "airfoil")
        self.config_model.design_variables = next_rows[:]
        self._make_parsec_rows()
        self._draw_design()

    def _read_model_from_fields(self) -> ProjectConfig:
        def build(section: str, cls: type):
            values = {}
            instance = cls()
            for item in fields(cls):
                raw = self.field_vars[(section, item.name)].get()
                default = getattr(instance, item.name)
                if section == "mesh" and item.name == "cpu_cores":
                    values[item.name] = None if raw == "Program Controlled" else int(raw)
                elif isinstance(default, bool):
                    values[item.name] = bool(raw)
                elif isinstance(default, int):
                    values[item.name] = int(raw)
                elif isinstance(default, float):
                    values[item.name] = float(raw)
                elif section == "mesh" and item.name == "method":
                    values[item.name] = "Default" if raw == "Default (ANSYS automatic)" else str(raw)
                else:
                    values[item.name] = str(raw)
            return cls(**values)

        variables = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            parsed = VariableSpec(spec.key, spec.label, float(value.get()), float(minimum.get()),
                                  float(maximum.get()), enabled.get())
            if parsed.minimum >= parsed.maximum:
                raise ValueError(f"{parsed.label}: minimum must be less than maximum.")
            if not parsed.minimum <= parsed.value <= parsed.maximum:
                raise ValueError(f"{parsed.label}: current value must be inside its bounds.")
            variables.append(parsed)
        model = ProjectConfig(
            project_name=self.project_name_var.get().strip() or "Untitled optimization",
            save_dir=self.save_dir_var.get(), tools=build("tools", ToolPaths),
            geometry=build("geometry", GeometrySettings), mesh=build("mesh", MeshSettings),
            cfd=build("cfd", CfdSettings), ga=build("ga", GaSettings),
            accessibility=AccessibilitySettings(theme=self.theme_var.get(), text_scale=int(self.text_scale_var.get()),
                                                high_contrast=self.high_contrast_var.get(), accent_color=self.accent_var.get(),
                                                candidate_marker_size=int(self.candidate_marker_size_var.get()),
                                                outer_marker_size=int(self.outer_marker_size_var.get())), design_variables=variables,
        )
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        model.geometry = replace(model.geometry, **geometry_values)
        if model.geometry.design_type == "flanged":
            validate_lower_profile(nested_parameters(variables))
        else:
            validate_profile(nested_parameters(variables))
        self._validate_positive_settings(model)
        if model.ga.objective not in OBJECTIVES:
            raise ValueError("Choose Cp, Ct, normalized Cp, or normalized Ct as the optimization criterion.")
        return model

    @staticmethod
    def _validate_positive_settings(config: ProjectConfig) -> None:
        if config.cfd.tip_loss_model not in {"prandtl", "bontempo2025"}:
            raise ValueError("Choose a valid tip-loss correction model.")
        if not all(math.isfinite(value) for value in (
                config.cfd.bontempo_g_a, config.cfd.bontempo_g_b, config.cfd.bontempo_g_c)):
            raise ValueError("Bontempo g coefficients must be finite numbers.")
        if config.geometry.design_type not in {"airfoil", "flanged"}:
            raise ValueError("Choose either the airfoil or flanged duct design.")
        if (config.geometry.duct_chord <= 0 or config.geometry.duct_thickness <= 0 or
                config.geometry.domain_length <= 0 or config.geometry.domain_height <= 0):
            raise ValueError("Geometry lengths must be positive.")
        if config.geometry.design_type == "flanged" and config.geometry.duct_flange_length <= 0:
            raise ValueError("Flange length must be positive.")
        mesh_sizes = (
            config.mesh.global_size_cm,
            config.mesh.growth_rate,
            config.mesh.resolution_size_cm,
            config.mesh.duct_size_cm,
            config.mesh.hub_size_cm,
            config.mesh.inflation_max_thickness_cm,
        )
        if min(mesh_sizes) <= 0:
            raise ValueError("All mesh sizes and inflation thickness must be positive.")
        if config.mesh.curvature_angle_deg <= 0:
            raise ValueError("Mesh curvature angle must be positive.")
        if config.mesh.cpu_cores is not None and config.mesh.cpu_cores < 1:
            raise ValueError("CPU cores for parallel part meshing must be at least one.")
        if config.mesh.method not in {"Default", "Quad", "Tri", "MultiZone"}:
            raise ValueError("Choose Default, Quad, Tri, or MultiZone as the meshing method.")
        if config.mesh.inflation_layers < 1:
            raise ValueError("Inflation must contain at least one layer.")
        if config.cfd.stations < 2 or config.cfd.max_outer_iterations < 1:
            raise ValueError("CFD stations and iteration counts are too small.")
        if min(config.cfd.flow_speed_m_s, config.cfd.density_kg_m3,
               config.cfd.viscosity_pa_s, config.cfd.rotor_radius_m) <= 0:
            raise ValueError("Flow properties and rotor radius must be positive.")
        if not 0 < config.cfd.hub_radius_m < config.cfd.rotor_radius_m:
            raise ValueError("Rotor hub radius must be positive and smaller than rotor radius.")
        if not 0 < config.cfd.relaxation <= 1:
            raise ValueError("CFD relaxation must be greater than 0 and no more than 1.")
        valid_cfd_choices = {
            name: set(values) for name, values in CFD_CHOICE_VALUES.items()
        }
        for name, options in valid_cfd_choices.items():
            if getattr(config.cfd, name) not in options:
                raise ValueError(f"Choose a valid value for {LABELS[name].lower()}.")
        active_residuals = ["residual_continuity", "residual_x_velocity", "residual_y_velocity",
                            "residual_swirl"]
        if config.cfd.viscous_model == "k_omega":
            active_residuals += ["residual_k", "residual_omega"]
        elif config.cfd.viscous_model == "k_epsilon":
            active_residuals += ["residual_k", "residual_epsilon"]
        else:
            active_residuals.append("residual_nut")
        if any(getattr(config.cfd, name) <= 0 for name in active_residuals):
            raise ValueError("Active Fluent residual criteria must be positive.")

    def _browse_tool(self, variable: tk.Variable) -> None:
        path = filedialog.askopenfilename(title="Select executable", filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            variable.set(path)

    def _choose_project_folder(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Run active", "Stop the active run before changing the project folder.")
            return
        selected = filedialog.askdirectory(title="Choose an empty or existing OpTurbo workflow folder")
        if selected:
            self.save_dir_var.set(selected)
            self._save_project()

    def _save_project(self) -> bool:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Run active", "Stop the active run before saving changed settings.")
            return False
        try:
            model = self._read_model_from_fields()
            previous_objective = self.config_model.ga.objective
            if not model.save_dir:
                self._choose_project_folder()
                return bool(self.save_dir_var.get())
            self.config_model = model
            if previous_objective != model.ga.objective:
                self.best_fitness = float("-inf")
                self.best_var.set(f"Best {OBJECTIVES[model.ga.objective]}: —")
            self.store = ProjectStore(Path(model.save_dir))
            self.store.initialize(model)
            self._update_resume_button()
            self.status_var.set(f"Saved — {model.save_dir}")
            return True
        except Exception as error:
            messagebox.showerror("Cannot save project", str(error))
            return False

    def _open_project(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Run active", "Stop the active run before opening another project.")
            return
        path = filedialog.askopenfilename(title="Open OpTurbo project", filetypes=[("OpTurbo project", "opturbo_project.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            self.config_model = ProjectStore.load(Path(path))
            self.store = ProjectStore(Path(self.config_model.save_dir))
            history_file = Path(self.config_model.save_dir) / "optimization_history.json"
            self.history = json.loads(history_file.read_text(encoding="utf-8")).get("evaluations", []) if history_file.exists() else []
            self._load_model_into_fields()
            self._refresh_results()
            self._update_resume_button()
            self.status_var.set(f"Opened — {self.config_model.save_dir}")
        except Exception as error:
            messagebox.showerror("Cannot open project", str(error))

    def _new_project(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Optimization running", "Stop the current run before creating a new project.")
            return
        self.config_model = ProjectConfig()
        self.store = None
        self.history.clear()
        self.best_fitness = float("-inf")
        self._update_resume_button()
        self._load_model_into_fields()
        self._refresh_results()
        self.status_var.set("New unsaved project")

    def _select_parsec(self, selected: bool) -> None:
        for _, enabled, *_ in self.parsec_rows:
            enabled.set(selected)

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

    def _require_saved_project(self) -> bool:
        if not self._save_project():
            return False
        return self.store is not None

    def _set_running(self, running: bool) -> None:
        self.single_button.configure(state="disabled" if running else "normal")
        self.start_button.configure(state="disabled" if running else "normal")
        self._update_resume_button(running)
        self.stop_button.configure(state="normal" if running else "disabled")
        self.terminate_button.configure(state="normal" if running else "disabled")

    def _update_resume_button(self, running: bool = False) -> None:
        """Enable resume when the selected project has an unfinished GA run."""
        if not hasattr(self, "resume_button"):
            return
        resumable = False
        if self.store is not None:
            try:
                state = self.store.load_optimization_state()
                resumable = bool(state and state.get("status") != "completed")
            except (OSError, ValueError, TypeError):
                resumable = False
        self.resume_button.configure(state="normal" if resumable and not running else "disabled")

    def _run_single(self) -> None:
        if not self._require_saved_project():
            return
        self._start_worker(self._single_worker, "Evaluating current design")

    def _run_ga(self) -> None:
        self._start_ga(resume=False)

    def _resume_ga(self) -> None:
        self._start_ga(resume=True)

    def _start_ga(self, resume: bool) -> None:
        if resume:
            if self.store is None:
                messagebox.showerror("No project selected", "Open the project that contains the optimization to resume.")
                return
            try:
                requested_config = self._read_model_from_fields()
                state = self.store.load_optimization_state()
            except Exception as error:
                messagebox.showerror("Cannot resume optimization", str(error))
                return
            if not state or state.get("status") == "completed":
                messagebox.showerror("No resumable optimization", "This project has no unfinished optimization to resume.")
                self._update_resume_button()
                return
            if state.get("configuration") != requested_config.to_dict():
                messagebox.showerror(
                    "Settings changed",
                    "The project settings differ from the saved optimization. Restore the original settings before resuming.",
                )
                return
            if not self._save_project():
                return
        elif not self._require_saved_project():
            return
        if not any(item.optimize for item in self.config_model.design_variables):
            messagebox.showerror("No variables selected", "Tick at least one variable in the Design tab.")
            return
        assert self.store is not None
        state = self.store.load_optimization_state()
        if resume:
            assert state is not None
        elif state and state.get("status") != "completed":
            if not messagebox.askyesno(
                "Start a new optimization?",
                "This project has an unfinished optimization. Starting a new run will replace its resume point. Continue?",
            ):
                return
        total = (self.config_model.ga.population_size +
                 (self.config_model.ga.generations - 1) *
                 (self.config_model.ga.population_size - self.config_model.ga.elite_count))
        completed = 0
        if resume and state:
            run_id = state.get("run_id")
            completed = sum(1 for row in self.history if row.get("optimization_id") == run_id)
        self.progress.configure(maximum=total, value=completed)
        self._start_worker(lambda: self._ga_worker(resume=resume),
                           "Resuming optimization" if resume else "Optimization running")

    def _start_worker(self, target: Callable[[], None], status: str) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_requested.clear()
        self.terminate_requested.clear()
        self._set_running(True)
        self.status_var.set(status)
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _runner(self) -> PipelineRunner:
        return PipelineRunner(APP_ROOT, lambda line: self.events.put(("log", line)), self.terminate_requested.is_set)

    def _single_worker(self) -> None:
        try:
            assert self.store is not None
            candidate = self.store.candidate_dir(0, 1)
            genome = {item.key: item.value for item in self.config_model.design_variables if item.optimize}
            self.events.put(("candidate", {"generation": 0, "candidate": 1, "genome": genome}))
            result = self._runner().evaluate(self.config_model, genome, candidate)
            event = {"evaluation": len(self.history) + 1, "generation": 0, "candidate": 1,
                     "fitness": objective_value(result, self.config_model.ga.objective),
                     "objective": self.config_model.ga.objective, "genome": genome, **result}
            self.events.put(("result", event))
            self.events.put(("done", "Current design evaluation completed"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _ga_worker(self, resume: bool = False) -> None:
        state: dict | None = None
        store: ProjectStore | None = None
        try:
            assert self.store is not None
            config = deepcopy(self.config_model)
            store = self.store
            if resume:
                state = store.load_optimization_state()
                if not state or state.get("status") == "completed":
                    raise RuntimeError("This project has no unfinished optimization to resume.")
                if state.get("configuration") != config.to_dict():
                    raise RuntimeError("Project settings changed since this optimization was started.")
                run_id = str(state["run_id"])
            else:
                run_id = uuid.uuid4().hex
                state = {
                    "run_id": run_id,
                    "status": "running",
                    "configuration": config.to_dict(),
                }
                store.save_optimization_state(state)

            with self.history_lock:
                resume_results = {
                    (int(row["generation"]), int(row["candidate"])): row
                    for row in self.history
                    if row.get("optimization_id") == run_id
                    and int(row.get("generation", 0)) >= 1
                    and "candidate" in row
                }
            optimizer = GeneticAlgorithm(config.design_variables, config.ga)
            runner = self._runner()

            def evaluate(genome: dict[str, float], generation: int, index: int):
                folder = store.candidate_dir(generation, index)
                self.events.put(("candidate", {"generation": generation, "candidate": index,
                                               "genome": genome.copy()}))
                try:
                    result = runner.evaluate(config, genome, folder)
                    return objective_value(result, config.ga.objective), result
                except Exception as error:
                    failure = failed_candidate(folder, error, config.ga.objective)
                    self.events.put(("log", f"{folder.name}: {failure['status']}; candidate skipped with penalty: {error}"))
                    return failure["fitness"], failure

            def generation_evaluator(candidates, generation):
                return evaluate_generation(runner, config, candidates, generation, store.candidate_dir,
                                           self.stop_requested.is_set,
                                           lambda event: self.events.put(("candidate", event)))

            def on_result(event: dict) -> None:
                key = (int(event["generation"]), int(event["candidate"]))
                if key in resume_results:
                    return
                saved_event = {**event, "optimization_id": run_id}
                with self.history_lock:
                    self.history.append(saved_event)
                    store.save_history(self.history)
                    resume_results[key] = saved_event
                self.events.put(("result", saved_event))

            best = optimizer.run(evaluate, on_result=on_result,
                                 should_stop=self.stop_requested.is_set,
                                 evaluate_generation=generation_evaluator if config.ga.overlap_preparation else None,
                                 resume_results=resume_results)
            if (not self.stop_requested.is_set() and best.result
                    and best.result.get("status") in {"failed", "skipped_fluent_crash"}):
                raise RuntimeError("Every candidate failed; optimization ran through the configured candidates but found no valid result.")
            run_status = "stopped" if self.stop_requested.is_set() else "finished"
            state_data = store.load_optimization_state() or {}
            state_data.update({
                "run_id": run_id,
                "status": "stopped" if self.stop_requested.is_set() else "completed",
                "configuration": config.to_dict(),
                "completed_candidates": len(resume_results),
            })
            store.save_optimization_state(state_data)
            label = OBJECTIVES[config.ga.objective]
            self.events.put(("done", f"Optimization {run_status}. Best {label} = {best.fitness:.6g}"))
        except Exception as error:
            if store is not None and state is not None:
                state["status"] = "interrupted"
                state["last_error"] = str(error)
                store.save_optimization_state(state)
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        self.stop_requested.set()
        self.status_var.set("Stop requested — waiting for the current candidate")
        self._append_log("Stop requested. Active CFD and any overlapping preparation will finish safely. No further CFD candidate will start.")

    def _terminate(self) -> None:
        """Cancel scheduling and kill active external process trees without deleting results."""
        self.stop_requested.set()
        self.terminate_requested.set()
        self.status_var.set("Terminating active processes; partial results will be retained")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "candidate":
                    candidate = payload  # type: ignore[assignment]
                    self.status_var.set(
                        f"Evaluating generation {candidate['generation']}, candidate {candidate['candidate']}")
                    self._show_candidate(candidate["genome"])
                elif kind == "result":
                    self._record_result(payload)  # type: ignore[arg-type]
                elif kind == "done":
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                    self._set_running(False)
                elif kind == "error":
                    self.status_var.set("Run failed")
                    self._append_log("ERROR: " + str(payload))
                    self._set_running(False)
                    messagebox.showerror("OpTurbo run failed", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _append_log(self, line: str) -> None:
        if "[4/4]" in line or "Stage 4" in line:
            self.outer_series.clear()
            self.outer_plot.set_series([])
        tokens = line.lower().split()
        if "iter" in tokens and "continuity" in tokens:
            if not self.residual_columns:
                self.residual_series.clear()
            self.residual_columns = tokens[1:]
        elif self.residual_columns and tokens and tokens[0].isdigit():
            for name, value in zip(self.residual_columns, tokens[1:]):
                if name in {"continuity", "x-velocity", "y-velocity", "z-velocity", "swirl", "k", "epsilon", "omega", "nut"}:
                    try:
                        number = float(value)
                        if number > 0 and math.isfinite(number):
                            self.residual_series.setdefault(name, []).append(math.log10(number))
                    except ValueError:
                        pass
            self.residual_plot.set_series(list(self.residual_series.items()))
        match = re.search(r"outer\s+(\d+):\s+(Cp|Ct)=([-+\d.eE]+)", line)
        if match:
            iteration, name, value = match.groups()
            if int(iteration) == 1 and name == "Cp":
                self.outer_series.clear()
            self.outer_series.setdefault(name, []).append(float(value))
            self.outer_plot.set_series(list(self.outer_series.items()))
            self.residual_columns = []
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _record_result(self, event: dict) -> None:
        with self.history_lock:
            optimization_id = event.get("optimization_id")
            already_saved = optimization_id and any(
                row.get("optimization_id") == optimization_id
                and row.get("generation") == event.get("generation")
                and row.get("candidate") == event.get("candidate")
                for row in self.history
            )
            if not already_saved:
                self.history.append(event)
            if self.store:
                self.store.save_history(self.history)
        cp = float(event.get("cp", float("nan")))
        ct_value = event.get("ct")
        ct = float(ct_value) if ct_value is not None else float("nan")
        status = event.get("status", "completed")
        self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                 event.get("candidate"), f"{cp:.7g}" if math.isfinite(cp) and cp > -1e20 else "—",
                                 f"{ct:.7g}" if math.isfinite(ct) else "—", status))
        with self.history_lock:
            progress_value = (sum(1 for row in self.history
                                  if row.get("optimization_id") == event.get("optimization_id"))
                              if event.get("optimization_id") else len(self.history))
        self.progress.configure(value=progress_value)
        fitness = float(event.get("fitness", cp))
        objective = str(event.get("objective", "cp"))
        if (status == "completed" and objective == self.config_model.ga.objective
                and fitness > self.best_fitness):
            self.best_fitness = fitness
            label = OBJECTIVES.get(objective, "objective")
            self.best_var.set(f"Best {label}: {fitness:.7g}    Cp: {cp:.7g}    Ct: {ct:.7g}")
            if self.store:
                atomic_json(self.store.root / "best" / "best_result.json", event)
        self._refresh_plots(event)

    def _show_candidate(self, genome: dict[str, float]) -> None:
        """Display the candidate currently passing through the external tools."""
        variables = [VariableSpec(item.key, item.label, genome.get(item.key, item.value),
                                  item.minimum, item.maximum, item.optimize)
                     for item in self.config_model.design_variables]
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(self.config_model.geometry, **geometry_values)
        try:
            top, bottom = self._duct_outline(geometry, variables)
        except Exception:
            return
        self._draw_domain(self.domain_canvas, geometry, top, bottom)
        self._draw_duct(self.duct_canvas, geometry, top, bottom)

    def _refresh_results(self) -> None:
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.best_fitness = float("-inf")
        for event in self.history:
            cp = float(event.get("cp", float("nan")))
            ct_value = event.get("ct")
            ct = float(ct_value) if ct_value is not None else float("nan")
            self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                     event.get("candidate"),
                                     f"{cp:.7g}" if math.isfinite(cp) and cp > -1e20 else "—",
                                     f"{ct:.7g}" if math.isfinite(ct) else "—",
                                     event.get("status", "completed")))
            fitness = float(event.get("fitness", cp))
            objective = str(event.get("objective", "cp"))
            if (event.get("status", "completed") == "completed"
                    and objective == self.config_model.ga.objective
                    and fitness > self.best_fitness):
                self.best_fitness = fitness
                label = OBJECTIVES.get(objective, "objective")
                self.best_var.set(f"Best {label}: {fitness:.7g}    Cp: {cp:.7g}    Ct: {ct:.7g}")
        self._refresh_plots(self.history[-1] if self.history else {})

    def _refresh_plots(self, latest: dict) -> None:
        cp_values = [float(row.get("cp", row.get("fitness", 0))) for row in self.history if float(row.get("cp", row.get("fitness", -1e30))) > -1e20]
        ct_values = [float(row.get("ct", 0)) for row in self.history if row.get("ct") is not None and str(row.get("ct")) != "nan"]
        self.performance_plot.set_series([("Cp", cp_values), ("Ct", ct_values)])
        bem_series = []
        loss_label = "Bontempo tip × Prandtl root" if latest.get("tip_loss_model") == "bontempo2025" else "Prandtl tip × root"
        for key, label in (("a", "a"), ("a_prime", "a′"), ("loss_factor", loss_label)):
            values = latest.get(key, latest.get("prandtl_loss") if key == "loss_factor" else None)
            if isinstance(values, list):
                bem_series.append((label, [float(value) for value in values]))
        self.bem_plot.set_series(bem_series)


def main() -> None:
    """Create and run the desktop application."""
    app = OpTurboApp()
    app.mainloop()
