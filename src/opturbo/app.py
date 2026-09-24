"""Tkinter desktop interface for configuring and running OpTurbo."""

from __future__ import annotations

from dataclasses import fields, replace
import json
from pathlib import Path
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .models import (
    CfdSettings,
    GaSettings,
    GeometrySettings,
    MeshSettings,
    ProjectConfig,
    ToolPaths,
    VariableSpec,
)
from .optimizer import GeneticAlgorithm
from .parsec import nested_parameters, profile, validate_profile
from .pipeline import PipelineRunner
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
    "duct_chord": "Duct chord (mm)",
    "duct_angle_deg": "Duct angle (deg)",
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
}


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

    def __init__(self, parent: tk.Misc, title: str, **kwargs):
        super().__init__(parent, background="white", highlightthickness=1,
                         highlightbackground="#c8ccd2", **kwargs)
        self.title = title
        self.series: list[tuple[str, list[float]]] = []
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_series(self, series: list[tuple[str, list[float]]]) -> None:
        self.series = series
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 200), max(self.winfo_height(), 140)
        left, top, right, bottom = 52, 30, width - 18, height - 35
        self.create_text(12, 10, text=self.title, anchor="nw", font=("Segoe UI", 10, "bold"), fill="#20242a")
        self.create_line(left, top, left, bottom, right, bottom, fill="#69717d")
        values = [value for _, items in self.series for value in items]
        if not values:
            self.create_text(width / 2, height / 2, text="No results yet", fill="#7b818a")
            return
        low, high = min(values), max(values)
        if abs(high - low) < 1e-12:
            low, high = low - 0.5, high + 0.5
        longest = max(len(items) for _, items in self.series)
        for tick in range(5):
            y = bottom - tick * (bottom - top) / 4
            value = low + tick * (high - low) / 4
            self.create_line(left, y, right, y, fill="#edf0f3")
            self.create_text(left - 6, y, text=f"{value:.3g}", anchor="e", fill="#606771", font=("Segoe UI", 8))
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
            self.create_text(legend_x + 23, 17, text=name, anchor="w", font=("Segoe UI", 8))


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
        self._configure_style()
        self._build_menu()
        self._build_layout()
        self._load_model_into_fields()
        self.after(100, self._poll_events)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1d2a3a")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground="#59636f")
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", padding=(8, 4), foreground="#344050")

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
        ttk.Label(left, text="Duct design variables", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Includes duct angle, chord, and PARSEC shape controls. Unticked rows are fixed.",
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
                                 exclude={"duct_angle_deg", "duct_chord"})
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
        self.performance_plot = LinePlot(performance, "Optimization objective history", height=260)
        self.performance_plot.pack(fill="both", expand=True)
        self.bem_plot = LinePlot(bem, "Latest radial BEM solution", height=260)
        self.bem_plot.pack(fill="both", expand=True)

    def _add_dataclass_form(self, parent: ttk.Frame, section: str, cls: type,
                            browse_paths: bool = False, exclude: set[str] | None = None) -> None:
        """Create labeled entries for every field in a settings dataclass."""
        row = 0
        for item in fields(cls):
            label = LABELS.get(item.name, item.name.replace("_", " ").title())
            default = getattr(cls(), item.name)
            if isinstance(default, bool):
                variable: tk.Variable = tk.BooleanVar()
                widget = ttk.Checkbutton(parent, variable=variable)
            else:
                variable = tk.StringVar()
                widget = ttk.Entry(parent, textvariable=variable)
            self.field_vars[(section, item.name)] = variable
            if exclude and item.name in exclude:
                continue
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=5)
            widget.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            if section == "tools" and item.name == "handoff_dir":
                widget.configure(state="readonly")
                ttk.Label(parent, text="Protected", foreground="#a34a2a").grid(row=row, column=2, padx=4)
            elif browse_paths:
                ttk.Button(parent, text="Browse…", command=lambda var=variable: self._browse_tool(var)).grid(row=row, column=2, padx=4)
            row += 1
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
            ttk.Checkbutton(self.parsec_body, variable=enabled).grid(row=row, column=0, padx=3, pady=3)
            label = ttk.Label(self.parsec_body, text=spec.label)
            value_entry = ttk.Entry(self.parsec_body, textvariable=value, width=11)
            minimum_entry = ttk.Entry(self.parsec_body, textvariable=minimum, width=11)
            maximum_entry = ttk.Entry(self.parsec_body, textvariable=maximum, width=11)
            label.grid(row=row, column=1, sticky="w", padx=3)
            minimum_entry.grid(row=row, column=2, padx=3)
            value_entry.grid(row=row, column=3, padx=3)
            maximum_entry.grid(row=row, column=4, padx=3)
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
                variable.set(getattr(settings, item.name))
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
        validate_profile(nested_parameters(variables))
        model = ProjectConfig(
            project_name=self.project_name_var.get().strip() or "Untitled optimization",
            save_dir=self.save_dir_var.get(), tools=build("tools", ToolPaths),
            geometry=build("geometry", GeometrySettings), mesh=build("mesh", MeshSettings),
            cfd=build("cfd", CfdSettings), ga=build("ga", GaSettings), design_variables=variables,
        )
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        model.geometry = replace(model.geometry, **geometry_values)
        self._validate_positive_settings(model)
        return model

    @staticmethod
    def _validate_positive_settings(config: ProjectConfig) -> None:
        if config.geometry.duct_chord <= 0 or config.geometry.domain_length <= 0 or config.geometry.domain_height <= 0:
            raise ValueError("Geometry lengths must be positive.")
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
        selected = filedialog.askdirectory(title="Choose an empty or existing OpTurbo workflow folder")
        if selected:
            self.save_dir_var.set(selected)
            self._save_project()

    def _save_project(self) -> bool:
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
        try:
            self.config_model = self._read_model_from_fields()
            self._draw_design()
            self.status_var.set("Design preview updated")
        except Exception as error:
            messagebox.showerror("Invalid design", str(error))

    def _preview_values(self) -> tuple[GeometrySettings, dict]:
        variables = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            try:
                variables.append(VariableSpec(spec.key, spec.label, float(value.get()),
                                              float(minimum.get()), float(maximum.get()), enabled.get()))
            except ValueError:
                return self.config_model.geometry, nested_parameters(self.config_model.design_variables)
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
        return geometry, nested_parameters(variables)

    def _draw_design(self) -> None:
        if not hasattr(self, "domain_canvas") or not self.parsec_rows:
            return
        geometry, parsec_values = self._preview_values()
        try:
            x_values, upper, lower = profile(parsec_values, 140)
        except Exception:
            return
        self._draw_domain(self.domain_canvas, geometry, x_values, upper, lower)
        self._draw_duct(self.duct_canvas, geometry, x_values, upper, lower)

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

    def _draw_domain(self, canvas: tk.Canvas, geometry: GeometrySettings, x: list[float], upper: list[float], lower: list[float]) -> None:
        canvas.delete("all")
        xmin, xmax = geometry.domain_origin_x, geometry.domain_origin_x + geometry.domain_length
        ymin, ymax = geometry.domain_origin_r, geometry.domain_origin_r + geometry.domain_height
        bounds = (xmin, xmax, ymin, ymax)
        domain = outer_domain_outline(geometry)
        canvas.create_polygon(*self._map_points(canvas, domain, bounds), fill="#f7fafc",
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
        top, bottom = self._duct_points(geometry, x, upper, lower)
        duct = top + list(reversed(bottom))
        canvas.create_polygon(*self._map_points(canvas, duct, bounds), fill="#efb1b5",
                              outline="#b52732", width=2)
        axis = [(xmin, geometry.domain_origin_r), (xmax, geometry.domain_origin_r)]
        canvas.create_line(*self._map_points(canvas, axis, bounds), fill="#20242a", width=2)
        canvas.create_text(14, 14, text="Axisymmetric domain preview (x–r, mm)", anchor="nw",
                           font=("Segoe UI", 10, "bold"), fill="#26313e")

    def _draw_duct(self, canvas: tk.Canvas, geometry: GeometrySettings, x: list[float], upper: list[float], lower: list[float]) -> None:
        canvas.delete("all")
        top, bottom = self._duct_points(geometry, x, upper, lower)
        points = top + bottom
        xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
        ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
        pad_x, pad_y = max((xmax - xmin) * 0.08, 1), max((ymax - ymin) * 0.25, 1)
        bounds = (xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y)
        polygon = top + list(reversed(bottom))
        canvas.create_polygon(*self._map_points(canvas, polygon, bounds), fill="#dcecff", outline="#245f9e", width=2)
        canvas.create_text(14, 14, text="PARSEC duct detail", anchor="nw", font=("Segoe UI", 10, "bold"), fill="#26313e")

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
            optimizer = GeneticAlgorithm(self.config_model.design_variables, self.config_model.ga)
            runner = self._runner()

            def evaluate(genome: dict[str, float], generation: int, index: int):
                folder = self.store.candidate_dir(generation, index)
                self.events.put(("candidate", {"generation": generation, "candidate": index,
                                               "genome": genome.copy()}))
                try:
                    result = runner.evaluate(self.config_model, genome, folder)
                    return result["cp"], result
                except Exception as error:
                    failure = {"cp": -1e30, "ct": float("nan"), "status": "failed",
                               "error": str(error), "candidate_dir": str(folder)}
                    (folder / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
                    self.events.put(("log", f"Candidate failed and received a penalty: {error}"))
                    return failure["cp"], failure

            best = optimizer.run(evaluate, on_result=lambda event: self.events.put(("result", event)),
                                 should_stop=self.stop_requested.is_set)
            self.events.put(("done", f"Optimization finished. Best Cp = {best.fitness:.6g}"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        self.stop_requested.set()
        self.status_var.set("Stop requested — waiting for the current candidate")
        self._append_log("Stop requested. The active candidate will finish so engineering files are not corrupted.")

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
        try:
            x_values, upper, lower = profile(nested_parameters(variables), 140)
        except Exception:
            return
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(self.config_model.geometry, **geometry_values)
        self._draw_domain(self.domain_canvas, geometry, x_values, upper, lower)
        self._draw_duct(self.duct_canvas, geometry, x_values, upper, lower)

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
        for key, label in (("a", "a"), ("a_prime", "a′"), ("prandtl_loss", "Prandtl F")):
            values = latest.get(key)
            if isinstance(values, list):
                bem_series.append((label, [float(value) for value in values]))
        self.bem_plot.set_series(bem_series)


def main() -> None:
    """Create and run the desktop application."""
    app = OpTurboApp()
    app.mainloop()
