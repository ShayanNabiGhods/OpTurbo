"""Focused Tkinter behavior for the OpTurbo application."""

import tkinter as tk
from tkinter import ttk

from ..models import GaSettings
from ..objectives import OBJECTIVES
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
        self._add_dataclass_form(settings, "ga", GaSettings, inline_help=False)
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
        columns = ("evaluation", "generation", "candidate", "cp", "ct", "cp_normalized", "ct_normalized", "status")
        results_table = ttk.Frame(results)
        results_table.pack(fill="both", expand=True)
        self.results_tree = ttk.Treeview(results_table, columns=columns, show="headings", height=16)
        headings = {"cp_normalized": "Cp normalized", "ct_normalized": "Ct normalized"}
        widths = (70, 70, 70, 85, 85, 110, 110, 150)
        for name, width in zip(columns, widths):
            self.results_tree.heading(name, text=headings.get(name, name.replace("_", " ").title()))
            self.results_tree.column(name, width=width, anchor="center")
        results_scroll = ttk.Scrollbar(results_table, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=results_scroll.set)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        results_scroll.grid(row=0, column=1, sticky="ns")
        results_table.rowconfigure(0, weight=1)
        results_table.columnconfigure(0, weight=1)
        self.best_var = tk.StringVar(
            value=f"Best {OBJECTIVES.get(self.config_model.ga.objective, 'objective')}: —")
        ttk.Label(results, textvariable=self.best_var, style="Title.TLabel").pack(anchor="w", pady=10)

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
