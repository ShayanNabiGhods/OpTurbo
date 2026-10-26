"""Focused Tkinter behavior for the OpTurbo application."""

import tkinter as tk
from tkinter import ttk

from ..models import GaSettings
from ..objectives import OBJECTIVES
from .plot import LinePlot
from .widgets import ScrollableFrame


class OptimizationViewMixin:
    def _build_optimization_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.optimization_tab = tab
        self.notebook.add(tab, text="  Optimization  ")
        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        settings_scroll = ScrollableFrame(pane)
        settings = settings_scroll.body
        settings.configure(padding=(12, 12, 12, 8))
        self.optimization_settings_body = settings
        settings.bind("<Configure>", self._resize_optimization_help, add="+")
        results = ttk.Frame(pane, padding=(12, 0))
        pane.add(settings_scroll, weight=1)
        pane.add(results, weight=2)
        self.run_only_note = ttk.Label(
            settings,
            text=("Run one open-turbine case or sweep tip-speed ratio. Each point is "
                  "saved as a separate candidate with geometry, mesh, Fluent/BEM results, and logs."),
            style="Subtitle.TLabel", wraplength=340, justify="left",
        )
        self.run_only_note.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(4, 12))
        self.run_sweep_frame = ttk.LabelFrame(settings, text="CFD/BEM TSR sweep", padding=8)
        self.run_sweep_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        self.run_tsr_min_var = tk.StringVar(value="4")
        self.run_tsr_max_var = tk.StringVar(value="8")
        self.run_tsr_step_var = tk.StringVar(value="0.5")
        for row, (label, variable) in enumerate((
            ("Minimum TSR", self.run_tsr_min_var),
            ("Maximum TSR", self.run_tsr_max_var),
            ("TSR interval", self.run_tsr_step_var),
        )):
            ttk.Label(self.run_sweep_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(self.run_sweep_frame, textvariable=variable, width=12,
                      validate="key", validatecommand=self.numeric_entry_validate).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
        self.run_sweep_button = ttk.Button(
            self.run_sweep_frame, text="Run CFD/BEM TSR sweep", command=self._run_tsr_sweep)
        self.run_sweep_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.run_sweep_frame.columnconfigure(1, weight=1)
        self.ga_settings_frame = ttk.LabelFrame(settings, text="Genetic optimization settings", padding=4)
        self.ga_settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        self._add_dataclass_form(self.ga_settings_frame, "ga", GaSettings, inline_help=False)
        actions = ttk.Frame(settings)
        actions.grid(row=3, column=0, columnspan=3, sticky="ew", pady=16)
        self.single_button = ttk.Button(actions, text="Evaluate current design", command=self._run_single)
        self.single_button.pack(fill="x", pady=3)
        self.ga_actions = ttk.Frame(actions)
        self.ga_actions.pack(fill="x")
        self.start_button = ttk.Button(self.ga_actions, text="Start GA optimization", style="Accent.TButton", command=self._run_ga)
        self.start_button.pack(fill="x", pady=3)
        self.resume_button = ttk.Button(self.ga_actions, text="Resume previous optimization", command=self._resume_ga,
                                        state="disabled")
        self.resume_button.pack(fill="x", pady=3)
        self.stop_button = ttk.Button(actions, text="Stop after current candidate", command=self._stop, state="disabled")
        self.stop_button.pack(fill="x", pady=3)
        self.terminate_button = ttk.Button(actions, text="Terminate whole process", command=self._terminate, state="disabled")
        self.terminate_button.pack(fill="x", pady=3)
        self.results_title = ttk.Label(results, text="Optimization progress", style="Title.TLabel")
        self.results_title.pack(anchor="w")
        self.progress = ttk.Progressbar(results, mode="determinate")
        self.progress.pack(fill="x", pady=8)
        columns = ("evaluation", "generation", "candidate", "tsr", "cp", "ct", "cp_normalized", "ct_normalized", "status")
        self.run_results_notebook = ttk.Notebook(results)
        self.run_results_notebook.pack(fill="both", expand=True)
        results_table = ttk.Frame(self.run_results_notebook, padding=(0, 0, 0, 4))
        run_plot_page = ttk.Frame(self.run_results_notebook)
        self.run_results_notebook.add(results_table, text="Run table")
        self.run_results_notebook.add(run_plot_page, text="Cp / Ct vs TSR")
        self.run_plot_page = run_plot_page
        self.results_tree = ttk.Treeview(results_table, columns=columns, show="headings", height=16)
        self.results_tree.bind("<Configure>", self._resize_run_results_columns, add="+")
        self.run_only_columns = ("evaluation", "tsr", "cp", "ct", "status")
        headings = {"cp_normalized": "Cp normalized", "ct_normalized": "Ct normalized"}
        headings.update({"evaluation": "Evaluation", "tsr": "TSR", "cp": "Cp", "ct": "Ct"})
        widths = (75, 80, 80, 80, 90, 90, 120, 120, 150)
        for name, width in zip(columns, widths):
            self.results_tree.heading(name, text=headings.get(name, name.replace("_", " ").title()))
            self.results_tree.column(name, width=width, anchor="center")
        results_scroll = ttk.Scrollbar(results_table, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=results_scroll.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        results_scroll.grid(row=0, column=1, sticky="ns")
        results_table.rowconfigure(0, weight=1)
        results_table.columnconfigure(0, weight=1)
        self.run_tsr_plot = LinePlot(
            run_plot_page, "Open-turbine CFD/BEM sweep", "Tip-speed ratio, TSR (-)",
            "Coefficient (-)", markers=True, smooth=False, y_step=0.1,
            y_max=1.0, x_step=1.0, height=360,
        )
        self.run_tsr_plot.pack(fill="both", expand=True)
        self.best_var = tk.StringVar(
            value=f"Best {OBJECTIVES.get(self.config_model.ga.objective, 'objective')}: —")
        ttk.Label(results, textvariable=self.best_var, style="Title.TLabel").pack(anchor="w", pady=10)

    def _resize_run_results_columns(self, event: tk.Event) -> None:
        """Fit visible run-result columns to the table's current width."""
        tree = getattr(self, "results_tree", None)
        if tree is None or event.width <= 1:
            return
        columns = (self.run_only_columns if self._run_only_selected()
                   else tuple(tree.cget("columns")))
        if not columns:
            return
        available = max(1, event.width - 24)
        weights = {"evaluation": 1.15, "generation": 1.0, "candidate": 1.0,
                   "tsr": 0.85, "cp": 0.85, "ct": 0.85,
                   "cp_normalized": 1.3, "ct_normalized": 1.3, "status": 1.5}
        total = sum(weights.get(column, 1.0) for column in columns)
        for column in columns:
            width = max(48, round(available * weights.get(column, 1.0) / total))
            tree.column(column, width=width, minwidth=48, stretch=True)

    def _resize_optimization_help(self, event: tk.Event | None = None) -> None:
        """Wrap optimization help to its actual column width and preserve a right margin."""
        body = getattr(self, "optimization_settings_body", None)
        if body is None:
            return
        width = event.width if event is not None else body.winfo_width()
        for widget in body.winfo_children():
            if isinstance(widget, ttk.Label) and widget.cget("style") == "Subtitle.TLabel":
                available = width - widget.winfo_x() - 12
                widget.configure(wraplength=max(100, available))
