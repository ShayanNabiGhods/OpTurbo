"""Focused Tkinter behavior for the OpTurbo application."""

import math
import re
import tkinter as tk
from tkinter import ttk

from .widgets import LinePlot


class MonitorViewMixin:
    def _build_monitor_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="  Monitor  ")
        tab.columnconfigure(0, weight=1, uniform="monitor_columns")
        tab.columnconfigure(1, weight=1, uniform="monitor_columns")
        tab.rowconfigure(0, weight=1, uniform="monitor_rows")
        tab.rowconfigure(1, weight=1, uniform="monitor_rows")
        log_frame = ttk.LabelFrame(tab, text="Fluent and pipeline log", padding=5)
        plots = ttk.Notebook(tab)
        self.monitor_plots = plots
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
        self.performance_plot = LinePlot(performance, "Performance history", "Evaluation (-)", "Cp / Ct (-)",
                                         markers=True, scatter=True, height=260)
        self.performance_plot.pack(fill="both", expand=True)
        self.bem_plot = LinePlot(bem, "Latest radial BEM solution", "Radial station (-)", "Value (-)",
                                 y_step=0.1, y_max=1.0, height=260)
        self.bem_plot.pack(fill="both", expand=True)
        self.residual_plot = LinePlot(residual, "Current Fluent run", "Solver iteration sample (-)", "Residual (-)", log_ticks=True)
        self.residual_plot.pack(fill="both", expand=True)
        self.outer_plot = LinePlot(outer, "Current candidate coupling", "Outer iteration (-)", "Cp / Ct (-)",
                                   y_step=0.1, markers=True, smooth=False)
        self.outer_plot.pack(fill="both", expand=True)

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
