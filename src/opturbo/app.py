"""Tkinter desktop interface for configuring and running OpTurbo."""

from __future__ import annotations

from dataclasses import fields, replace
from copy import deepcopy
import json
from pathlib import Path
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

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
from .parsec import lower_profile, nested_parameters, profile, validate_lower_profile, validate_profile
from .pipeline import PipelineRunner
from .pipeline.overlap import evaluate_generation
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
    "max_outer_iterations": "Maximum outer iterations",
    "fluent_iterations": "Fluent iterations per outer loop",
    "tolerance": "Cp/Ct convergence tolerance",
    "relaxation": "Source relaxation",
    "processors": "Fluent processor count",
    "keep_iteration_data": "Keep every outer-iteration solution data file",
    "population_size": "Population size",
    "generations": "Generations",
    "elite_count": "Elite designs retained",
    "tournament_size": "Tournament size",
    "crossover_rate": "Crossover probability",
    "mutation_rate": "Mutation probability",
    "mutation_scale": "Mutation scale (fraction of range)",
    "random_seed": "Random seed",
    "overlap_preparation": "Overlap meshing with Fluent (experimental)",
}


FIELD_HELP = {
    "overlap_preparation": "Prepare one next candidate through meshing while the current candidate runs Fluent. Same generation only. Stop waits for both active jobs; a prepared mesh is retained. Uses extra RAM and may require concurrent ANSYS licenses.",
    "tip_loss_model": "prandtl: original tip and root factors. bontempo2025: duct-calibrated F1 from page 5, Eq. (6), without a root factor.",
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
    "duct_reverse": "Mirrors the PARSEC surface about its reference line before geometry is created.",
    "duct_points": "Number of spline samples used to construct the duct; higher values make a smoother curve.",
    "global_size_cm": "Default mesh element size away from locally refined regions, in centimetres.",
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
    "population_size": "Number of candidate designs evaluated in each GA generation.",
    "generations": "Number of GA generations to evaluate.",
    "elite_count": "Best candidates copied unchanged into the next generation.",
    "tournament_size": "Number of candidates compared when selecting each parent.",
    "crossover_rate": "Probability that each child combines values from both parents.",
    "mutation_rate": "Probability that each gene is randomly perturbed in a child.",
    "mutation_scale": "Standard deviation of a mutation as a fraction of that variable's range.",
    "random_seed": "Fixed seed that makes the optimization sequence reproducible.",
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

    def __init__(self, parent: tk.Misc, title: str, x_label: str, y_label: str, **kwargs):
        super().__init__(parent, background="white", highlightthickness=1,
                         highlightbackground="#c8ccd2", **kwargs)
        self.title, self.x_label, self.y_label = title, x_label, y_label
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
        left, top, right, bottom = 52, 30, width - 18, height - 35
        self.create_text(12, 10, text=self.title, anchor="nw", font=("Segoe UI", 10, "bold"), fill=self.palette["text"])
        self.create_line(left, top, left, bottom, right, bottom, fill=self.palette["axis"])
        self.create_text((left + right) / 2, height - 8, text=self.x_label, fill=self.palette["muted"], font=("Segoe UI", 8))
        self.create_text(8, (top + bottom) / 2, text=self.y_label, angle=90, fill=self.palette["muted"], font=("Segoe UI", 8))
        values = [value for _, items in self.series for value in items]
        if not values:
            self.create_text(width / 2, height / 2, text="No results yet", fill=self.palette["muted"])
            return
        low, high = min(values), max(values)
        if abs(high - low) < 1e-12:
            low, high = low - 0.5, high + 0.5
        longest = max(len(items) for _, items in self.series)
        for tick in range(5):
            y = bottom - tick * (bottom - top) / 4
            value = low + tick * (high - low) / 4
            self.create_line(left, y, right, y, fill=self.palette["grid"])
            self.create_text(left - 6, y, text=f"{value:.3g}", anchor="e", fill=self.palette["muted"], font=("Segoe UI", 8))
        for series_index, (name, items) in enumerate(self.series):
            color = self.COLORS[series_index % len(self.COLORS)]
            coordinates: list[float] = []
            for index, value in enumerate(items):
                x = left if longest <= 1 else left + index * (right - left) / (longest - 1)
                y = bottom - (value - low) * (bottom - top) / (high - low)
                coordinates.extend((x, y))
            if len(coordinates) >= 4:
                self.create_line(*coordinates, fill=color, width=2, smooth=True)
            elif coordinates:
                self.create_oval(coordinates[0] - 2, coordinates[1] - 2,
                                 coordinates[0] + 2, coordinates[1] + 2, fill=color)
            legend_x = right - 90 * (len(self.series) - series_index)
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
        self.worker: threading.Thread | None = None
        self.history: list[dict] = []
        self.best_cp = float("-inf")
        self.field_vars: dict[tuple[str, str], tk.Variable] = {}
        self.parsec_rows: list[tuple[VariableSpec, tk.BooleanVar, tk.StringVar, tk.StringVar, tk.StringVar]] = []
        self.variable_controls: dict[str, tuple[ttk.Widget, ...]] = {}
        self.design_variable_sets: dict[str, list[VariableSpec]] = {}
        self.palette = self._theme_palette(AccessibilitySettings())
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._load_model_into_fields()
        self.after(100, self._poll_events)

    @staticmethod
    def _theme_palette(settings: AccessibilitySettings) -> dict[str, str]:
        """Return accessible colours for the selected appearance settings."""
        if settings.high_contrast:
            return {"background": "#000000", "canvas": "#000000", "surface": "#111111", "text": "#ffffff",
                    "muted": "#e0e0e0", "accent": "#00d9ff", "grid": "#4a4a4a", "axis": "#ffffff"}
        if settings.theme == "dark":
            return {"background": "#1b1e23", "canvas": "#20242a", "surface": "#292e36", "text": "#eef2f7",
                    "muted": "#c0c8d2", "accent": "#70b7ff", "grid": "#3a424d", "axis": "#b8c1cc"}
        return {"background": "#f4f6f8", "canvas": "#ffffff", "surface": "#ffffff", "text": "#1d2a3a",
                "muted": "#59636f", "accent": "#2f6fed", "grid": "#edf0f3", "axis": "#69717d"}

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
        style.configure("Status.TLabel", padding=(8, 4), foreground=colors["muted"])

    def _apply_accessibility(self, _event: object | None = None) -> None:
        """Apply appearance preferences immediately without restarting the app."""
        settings = AccessibilitySettings(theme=self.theme_var.get(), text_scale=int(self.text_scale_var.get()),
                                         high_contrast=self.high_contrast_var.get())
        self.palette = self._theme_palette(settings)
        self.config_model.accessibility = settings
        self._configure_style()
        for canvas in (getattr(self, "domain_canvas", None), getattr(self, "duct_canvas", None)):
            if canvas:
                canvas.configure(background=self.palette["canvas"])
        for plot in (getattr(self, "performance_plot", None), getattr(self, "bem_plot", None)):
            if plot:
                plot.set_palette({key: self.palette[key] for key in ("canvas", "text", "muted", "grid", "axis")})
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
        scroll = ScrollableFrame(left)
        scroll.pack(fill="both", expand=True)
        self.parsec_body = scroll.body
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
        scroll = ScrollableFrame(tab)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        body.columnconfigure(0, weight=1, uniform="workflow_columns")
        body.columnconfigure(1, weight=1, uniform="workflow_columns")
        geometry = ttk.LabelFrame(body, text="Geometry", padding=10)
        mesh = ttk.LabelFrame(body, text="Meshing", padding=10)
        cfd = ttk.LabelFrame(body, text="CFD / BEM", padding=10)
        geometry.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 7), pady=4)
        mesh.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=4)
        cfd.grid(row=1, column=1, sticky="nsew", padx=(7, 0), pady=4)
        self._add_dataclass_form(geometry, "geometry", GeometrySettings,
                                 exclude={"design_type", "duct_angle_deg", "duct_chord", "duct_thickness",
                                          "duct_flange_length", "duct_flange_angle_deg"})
        self._add_dataclass_form(mesh, "mesh", MeshSettings)
        self._add_dataclass_form(cfd, "cfd", CfdSettings)

    def _build_optimization_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="  Optimization  ")
        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        settings = ScrollableFrame(pane)
        results = ttk.Frame(pane, padding=(12, 0))
        pane.add(settings, weight=1)
        pane.add(results, weight=2)
        self._add_dataclass_form(settings.body, "ga", GaSettings)
        actions = ttk.Frame(settings.body)
        actions.grid(row=50, column=0, columnspan=3, sticky="ew", pady=16)
        self.single_button = ttk.Button(actions, text="Evaluate current design", command=self._run_single)
        self.single_button.pack(fill="x", pady=3)
        self.start_button = ttk.Button(actions, text="Start GA optimization", style="Accent.TButton", command=self._run_ga)
        self.start_button.pack(fill="x", pady=3)
        self.stop_button = ttk.Button(actions, text="Stop after current candidate", command=self._stop, state="disabled")
        self.stop_button.pack(fill="x", pady=3)
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
        self.best_var = tk.StringVar(value="Best Cp: —")
        ttk.Label(results, textvariable=self.best_var, style="Title.TLabel").pack(anchor="w", pady=10)

    def _build_monitor_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  Monitor  ")
        tab.columnconfigure(0, weight=1, uniform="monitor_columns")
        tab.columnconfigure(1, weight=1, uniform="monitor_columns")
        tab.rowconfigure(0, weight=1, uniform="monitor_rows")
        tab.rowconfigure(1, weight=1, uniform="monitor_rows")
        log_frame = ttk.LabelFrame(tab, text="Fluent and pipeline log", padding=5)
        performance = ttk.LabelFrame(tab, text="Cp / Ct history", padding=5)
        bem = ttk.LabelFrame(tab, text="BEM distributions", padding=5)
        log_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
        performance.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
        bem.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(5, 0))
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
        self.performance_plot = LinePlot(performance, "Optimization objective history", "Evaluation (-)", "Cp / Ct (-)", height=260)
        self.performance_plot.pack(fill="both", expand=True)
        self.bem_plot = LinePlot(bem, "Latest radial BEM solution", "Radial station (-)", "Value (-)", height=260)
        self.bem_plot.pack(fill="both", expand=True)

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
        ttk.Label(panel, text="Theme").grid(row=2, column=0, sticky="w", pady=5)
        theme = ttk.Combobox(panel, textvariable=self.theme_var, values=("light", "dark"), state="readonly", width=14)
        theme.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Label(panel, text="Light uses the default palette; dark reduces screen brightness.", style="Subtitle.TLabel", wraplength=420).grid(row=3, column=1, sticky="w")
        ttk.Label(panel, text="Text size").grid(row=4, column=0, sticky="w", pady=(12, 5))
        text_scale = ttk.Combobox(panel, textvariable=self.text_scale_var, values=("90", "100", "110", "125", "150"), state="readonly", width=14)
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

    def _add_dataclass_form(self, parent: ttk.Frame, section: str, cls: type,
                            browse_paths: bool = False, exclude: set[str] | None = None) -> None:
        """Create labeled entries for every field in a settings dataclass."""
        row = 0
        for item in fields(cls):
            label = LABELS.get(item.name, item.name.replace("_", " ").title())
            default = getattr(cls(), item.name)
            if section == "cfd" and item.name == "tip_loss_model":
                variable = tk.StringVar()
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=("prandtl", "bontempo2025"))
            elif isinstance(default, bool):
                variable: tk.Variable = tk.BooleanVar()
                widget = ttk.Checkbutton(parent, variable=variable)
            else:
                variable = tk.StringVar()
                widget = ttk.Entry(parent, textvariable=variable)
            self.field_vars[(section, item.name)] = variable
            if exclude and item.name in exclude:
                continue
            label_widget = ttk.Label(parent, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=5, pady=5)
            widget.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            help_text = FIELD_HELP.get(item.name, f"Controls {label.lower()}.")
            ttk.Label(parent, text=help_text, style="Subtitle.TLabel", wraplength=360,
                      justify="left").grid(row=row + 1, column=1, columnspan=2, sticky="w", padx=5, pady=(0, 5))
            ToolTip(label_widget, help_text)
            ToolTip(widget, help_text)
            if section == "tools" and item.name == "handoff_dir":
                widget.configure(state="readonly")
                ttk.Label(parent, text="Protected", foreground="#a34a2a").grid(row=row, column=2, padx=4)
            elif browse_paths:
                ttk.Button(parent, text="Browse…", command=lambda var=variable: self._browse_tool(var)).grid(row=row, column=2, padx=4)
            row += 2
        parent.columnconfigure(1, weight=1)

    def _make_parsec_rows(self) -> None:
        for child in self.parsec_body.winfo_children():
            child.destroy()
        self.parsec_rows.clear()
        self.variable_controls.clear()
        for column, text in ((0, "Use"), (1, "Parameter"), (2, "Minimum"), (3, "Value"), (4, "Maximum"), (5, "Description")):
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
            description = ttk.Label(self.parsec_body, text=hint, style="Subtitle.TLabel", wraplength=250, justify="left")
            description.grid(row=row, column=5, sticky="w", padx=(8, 3))
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
        self.parsec_body.columnconfigure(5, weight=1)

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
                variable.set(getattr(settings, item.name))
        self.design_type_var.set(self.config_model.geometry.design_type)
        self.theme_var.set(self.config_model.accessibility.theme)
        self.text_scale_var.set(str(self.config_model.accessibility.text_scale))
        self.high_contrast_var.set(self.config_model.accessibility.high_contrast)
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
                if isinstance(default, bool):
                    values[item.name] = bool(raw)
                elif isinstance(default, int):
                    values[item.name] = int(raw)
                elif isinstance(default, float):
                    values[item.name] = float(raw)
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
                                                high_contrast=self.high_contrast_var.get()), design_variables=variables,
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
        return model

    @staticmethod
    def _validate_positive_settings(config: ProjectConfig) -> None:
        if config.cfd.tip_loss_model not in {"prandtl", "bontempo2025"}:
            raise ValueError("Choose a valid tip-loss correction model.")
        if config.geometry.design_type not in {"airfoil", "flanged"}:
            raise ValueError("Choose either the airfoil or flanged duct design.")
        if (config.geometry.duct_chord <= 0 or config.geometry.duct_thickness <= 0 or
                config.geometry.domain_length <= 0 or config.geometry.domain_height <= 0):
            raise ValueError("Geometry lengths must be positive.")
        if config.geometry.design_type == "flanged" and config.geometry.duct_flange_length <= 0:
            raise ValueError("Flange length must be positive.")
        mesh_sizes = (
            config.mesh.global_size_cm,
            config.mesh.resolution_size_cm,
            config.mesh.duct_size_cm,
            config.mesh.hub_size_cm,
            config.mesh.inflation_max_thickness_cm,
        )
        if min(mesh_sizes) <= 0:
            raise ValueError("All mesh sizes and inflation thickness must be positive.")
        if config.mesh.curvature_angle_deg <= 0:
            raise ValueError("Mesh curvature angle must be positive.")
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
            if not model.save_dir:
                self._choose_project_folder()
                return bool(self.save_dir_var.get())
            self.config_model = model
            self.store = ProjectStore(Path(model.save_dir))
            self.store.initialize(model)
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
        self.best_cp = float("-inf")
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
        """Mirror the FreeCAD lower-PARSEC/flange construction for the preview."""
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
                raise ValueError("PARSEC and flange tangents must not be parallel.")
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
        self.stop_button.configure(state="normal" if running else "disabled")

    def _run_single(self) -> None:
        if not self._require_saved_project():
            return
        self._start_worker(self._single_worker, "Evaluating current design")

    def _run_ga(self) -> None:
        if not self._require_saved_project():
            return
        if not any(item.optimize for item in self.config_model.design_variables):
            messagebox.showerror("No variables selected", "Tick at least one variable in the Design tab.")
            return
        total = (self.config_model.ga.population_size +
                 (self.config_model.ga.generations - 1) *
                 (self.config_model.ga.population_size - self.config_model.ga.elite_count))
        self.progress.configure(maximum=total, value=0)
        self._start_worker(self._ga_worker, "Optimization running")

    def _start_worker(self, target: Callable[[], None], status: str) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_requested.clear()
        self._set_running(True)
        self.status_var.set(status)
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _runner(self) -> PipelineRunner:
        return PipelineRunner(APP_ROOT, lambda line: self.events.put(("log", line)))

    def _single_worker(self) -> None:
        try:
            assert self.store is not None
            candidate = self.store.candidate_dir(0, 1)
            genome = {item.key: item.value for item in self.config_model.design_variables if item.optimize}
            self.events.put(("candidate", {"generation": 0, "candidate": 1, "genome": genome}))
            result = self._runner().evaluate(self.config_model, genome, candidate)
            event = {"evaluation": len(self.history) + 1, "generation": 0, "candidate": 1,
                     "fitness": result["cp"], "genome": genome, **result}
            self.events.put(("result", event))
            self.events.put(("done", "Current design evaluation completed"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _ga_worker(self) -> None:
        try:
            assert self.store is not None
            config = deepcopy(self.config_model)
            store = self.store
            optimizer = GeneticAlgorithm(config.design_variables, config.ga)
            runner = self._runner()

            def evaluate(genome: dict[str, float], generation: int, index: int):
                folder = store.candidate_dir(generation, index)
                self.events.put(("candidate", {"generation": generation, "candidate": index,
                                               "genome": genome.copy()}))
                try:
                    result = runner.evaluate(config, genome, folder)
                    return result["cp"], result
                except Exception as error:
                    failure = {"cp": -1e30, "ct": float("nan"), "status": "failed",
                               "error": str(error), "candidate_dir": str(folder)}
                    (folder / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
                    self.events.put(("log", f"Candidate failed and received a penalty: {error}"))
                    return failure["cp"], failure

            def generation_evaluator(candidates, generation):
                return evaluate_generation(runner, config, candidates, generation, store.candidate_dir,
                                           self.stop_requested.is_set,
                                           lambda event: self.events.put(("candidate", event)))

            best = optimizer.run(evaluate, on_result=lambda event: self.events.put(("result", event)),
                                 should_stop=self.stop_requested.is_set,
                                 evaluate_generation=generation_evaluator if config.ga.overlap_preparation else None)
            state = "stopped" if self.stop_requested.is_set() else "finished"
            self.events.put(("done", f"Optimization {state}. Best Cp = {best.fitness:.6g}"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        self.stop_requested.set()
        self.status_var.set("Stop requested — waiting for the current candidate")
        self._append_log("Stop requested. Active CFD and any overlapping preparation will finish safely. No further CFD candidate will start.")

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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _record_result(self, event: dict) -> None:
        self.history.append(event)
        if self.store:
            self.store.save_history(self.history)
        cp = float(event.get("cp", event.get("fitness", float("nan"))))
        ct = float(event.get("ct", float("nan")))
        status = event.get("status", "completed")
        self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                 event.get("candidate"), f"{cp:.7g}", f"{ct:.7g}", status))
        self.progress.configure(value=len(self.history))
        if cp > self.best_cp:
            self.best_cp = cp
            self.best_var.set(f"Best Cp: {cp:.7g}    Ct: {ct:.7g}")
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
        self.best_cp = float("-inf")
        for event in self.history:
            cp = float(event.get("cp", event.get("fitness", float("-inf"))))
            ct = float(event.get("ct", float("nan")))
            self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                     event.get("candidate"), f"{cp:.7g}", f"{ct:.7g}", event.get("status", "completed")))
            if cp > self.best_cp:
                self.best_cp = cp
                self.best_var.set(f"Best Cp: {cp:.7g}    Ct: {ct:.7g}")
        self._refresh_plots(self.history[-1] if self.history else {})

    def _refresh_plots(self, latest: dict) -> None:
        cp_values = [float(row.get("cp", row.get("fitness", 0))) for row in self.history if float(row.get("cp", row.get("fitness", -1e30))) > -1e20]
        ct_values = [float(row.get("ct", 0)) for row in self.history if row.get("ct") is not None and str(row.get("ct")) != "nan"]
        self.performance_plot.set_series([("Cp", cp_values), ("Ct", ct_values)])
        bem_series = []
        loss_label = "Bontempo F1" if latest.get("tip_loss_model") == "bontempo2025" else "Prandtl F"
        for key, label in (("a", "a"), ("a_prime", "a′"), ("loss_factor", loss_label)):
            values = latest.get(key, latest.get("prandtl_loss") if key == "loss_factor" else None)
            if isinstance(values, list):
                bem_series.append((label, [float(value) for value in values]))
        self.bem_plot.set_series(bem_series)


def main() -> None:
    """Create and run the desktop application."""
    app = OpTurboApp()
    app.mainloop()
