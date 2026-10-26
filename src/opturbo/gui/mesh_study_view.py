"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields
import tkinter as tk
from tkinter import ttk

from ..models import MeshSettings
from ..workflows.axisymmetric_2d.mesh_study import mesh_variable_bounds
from .constants import CPU_CORE_CHOICES, LABELS, MESH_STUDY_SIZE_FIELDS
from .widgets import ScrollableFrame


class MeshStudyViewMixin:
    def _build_mesh_study_tab(self) -> None:
        """Build controls and candidate review table for a fixed-design mesh study."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.mesh_study_tab = tab
        self.notebook.add(tab, text="  Mesh Study  ")
        self.mesh_study_description = ttk.Label(
            tab,
            text=("Compare mesh settings for one design. Geometry and CFD/BEM settings come from Workflow Settings; "
                  "only the mesh settings below vary. Candidate time is mesh plus Fluent/BEM time."),
            style="Subtitle.TLabel", wraplength=1120, justify="left",
        )
        self.mesh_study_description.pack(anchor="w", pady=(0, 8))
        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        controls_scroll = ScrollableFrame(pane)
        controls = ttk.LabelFrame(controls_scroll.body, text="Mesh candidate setup", padding=8)
        controls.pack(fill="x")
        review = ttk.Frame(pane, padding=(6, 0, 0, 0))
        pane.add(controls_scroll, weight=1)
        pane.add(review, weight=3)
        self.mesh_study_vars["method"] = tk.StringVar()
        method_label = ttk.Label(controls, text="Mesh method")
        method_label.grid(row=0, column=1, sticky="w", padx=4, pady=3)
        self.mesh_study_labels["method"] = method_label
        method = ttk.Combobox(controls, textvariable=self.mesh_study_vars["method"], state="readonly",
                              values=("Default (ANSYS automatic)", "Quad", "Tri", "MultiZone"), width=25)
        method.grid(row=0, column=2, columnspan=3, sticky="ew", padx=4, pady=3)
        self.mesh_study_controls["method"] = method
        self.mesh_study_vars["cpu_cores"] = tk.StringVar()
        cpu_label = ttk.Label(controls, text=LABELS.get("cpu_cores", "CPU cores"))
        cpu_label.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        self.mesh_study_labels["cpu_cores"] = cpu_label
        cpu = ttk.Combobox(controls, textvariable=self.mesh_study_vars["cpu_cores"],
                           values=CPU_CORE_CHOICES, state="readonly", width=18)
        cpu.grid(row=1, column=2, columnspan=3, sticky="ew", padx=4, pady=3)
        self.mesh_study_controls["cpu_cores"] = cpu
        for column, heading in ((2, "Minimum"), (3, "Current"), (4, "Maximum")):
            ttk.Label(controls, text=heading, style="Subtitle.TLabel").grid(
                row=2, column=column, sticky="w", padx=4, pady=(8, 2))
        size_fields = [item for item in fields(MeshSettings) if item.name in MESH_STUDY_SIZE_FIELDS]
        defaults = mesh_variable_bounds(MeshSettings())
        for row, item in enumerate(size_fields, 3):
            name = item.name
            self.mesh_study_enabled[name] = tk.BooleanVar(value=True)
            self.mesh_study_vars[name] = tk.StringVar()
            self.mesh_study_min_vars[name] = tk.StringVar(value=self._format_user_number(defaults[name][0]))
            self.mesh_study_max_vars[name] = tk.StringVar(value=self._format_user_number(defaults[name][1]))
            check = ttk.Checkbutton(controls, variable=self.mesh_study_enabled[name],
                                    command=self._refresh_mesh_study_controls)
            check.grid(row=row, column=0, sticky="w", padx=4, pady=3)
            self.mesh_study_checks[name] = check
            label = ttk.Label(controls, text=LABELS.get(name, name.replace("_", " ").title()))
            label.grid(row=row, column=1, sticky="w", padx=4, pady=3)
            self.mesh_study_labels[name] = label
            widget = ttk.Entry(controls, textvariable=self.mesh_study_vars[name], width=8,
                               validate="key", validatecommand=self.numeric_entry_validate)
            widget.grid(row=row, column=3, sticky="ew", padx=3, pady=3)
            self.mesh_study_controls[name] = widget
            minimum = ttk.Entry(controls, textvariable=self.mesh_study_min_vars[name], width=8,
                                validate="key", validatecommand=self.numeric_entry_validate)
            minimum.grid(row=row, column=2, sticky="ew", padx=3, pady=3)
            maximum = ttk.Entry(controls, textvariable=self.mesh_study_max_vars[name], width=8,
                                validate="key", validatecommand=self.numeric_entry_validate)
            maximum.grid(row=row, column=4, sticky="ew", padx=3, pady=3)
            self.mesh_study_bound_controls[name] = (minimum, maximum)
        self._refresh_mesh_study_controls()
        self.mesh_study_count_var = tk.StringVar(value="20")
        count_row = len(size_fields) + 3
        ttk.Label(controls, text="Automatic sweep cases").grid(
            row=count_row, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 3))
        ttk.Spinbox(controls, from_=1, to=100, textvariable=self.mesh_study_count_var, width=8).grid(
            row=count_row, column=2, sticky="w", padx=4, pady=(8, 3))
        ttk.Label(controls, text="Sweep method").grid(
            row=count_row + 1, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Label(controls, text="Evenly spaced").grid(
            row=count_row + 1, column=2, columnspan=3, sticky="w", padx=4, pady=3)
        self.mesh_study_manual_button = ttk.Button(
            controls, text="Run this mesh setup", command=self._start_manual_mesh_study)
        self.mesh_study_manual_button.grid(row=count_row + 2, column=0, columnspan=5, sticky="ew", padx=4, pady=(8, 3))
        self.mesh_study_auto_button = ttk.Button(
            controls, text="Run automatic mesh sweep", command=self._start_automatic_mesh_study)
        self.mesh_study_auto_button.grid(row=count_row + 3, column=0, columnspan=5, sticky="ew", padx=4, pady=3)
        self.mesh_study_resume_button = ttk.Button(
            controls, text="Resume mesh study", command=self._resume_mesh_study, state="disabled")
        self.mesh_study_resume_button.grid(row=count_row + 4, column=0, columnspan=5,
                                           sticky="ew", padx=4, pady=3)
        self.mesh_study_stop_button = ttk.Button(
            controls, text="Stop after current case", command=self._stop, state="disabled")
        self.mesh_study_stop_button.grid(row=count_row + 5, column=0, columnspan=5, sticky="ew", padx=4, pady=3)
        self.mesh_study_terminate_button = ttk.Button(
            controls, text="Terminate whole process", command=self._terminate, state="disabled")
        self.mesh_study_terminate_button.grid(row=count_row + 6, column=0, columnspan=5,
                                              sticky="ew", padx=4, pady=3)
        self.mesh_study_progress = ttk.Progressbar(controls, mode="determinate")
        self.mesh_study_progress.grid(row=count_row + 7, column=0, columnspan=5, sticky="ew", padx=4, pady=(8, 3))
        ttk.Label(controls, text="Evenly spaced sweeps move all enabled values from minimum to maximum.",
                  style="Subtitle.TLabel", wraplength=280, justify="left").grid(
            row=count_row + 8, column=0, columnspan=5, sticky="w", padx=4, pady=(3, 8))
        ttk.Button(controls, text="Load mesh values from Workflow Settings",
                   command=self._load_mesh_study_values_from_workflow).grid(
            row=count_row + 9, column=0, columnspan=5, sticky="ew", padx=4, pady=3)
        for column in (2, 3, 4):
            controls.columnconfigure(column, weight=1, uniform="mesh_study_values")

        ttk.Label(review, text="Mesh study candidates", style="Title.TLabel").pack(anchor="w", pady=(0, 4))
        table_frame = ttk.Frame(review)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "status", "cells", "mesh_s", "fluent_s", "total_s", "outer",
                   "cp", "ct", "cp_norm", "ct_norm")
        self.mesh_study_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        headings = ("ID", "Status", "Cells", "Mesh (s)", "Fluent/BEM (s)", "Total (s)", "Outer",
                    "Cp", "Ct", "Cp norm.", "Ct norm.")
        for name, heading in zip(columns, headings):
            self.mesh_study_tree.heading(name, text=heading)
            self.mesh_study_tree.column(name, width=70, anchor="center", stretch=False)
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.mesh_study_tree.yview)
        self.mesh_study_tree.configure(yscrollcommand=yscroll.set)
        self.mesh_study_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.mesh_study_tree.bind("<Configure>", self._resize_mesh_study_columns, add="+")
        self.mesh_study_tree.bind("<<TreeviewSelect>>", self._show_mesh_study_selection)
        details_row = ttk.Frame(review)
        details_row.pack(fill="x", pady=(8, 0))
        self.mesh_study_details = tk.Text(details_row, height=9, wrap="word", state="disabled")
        self.mesh_study_details.pack(side="left", fill="both", expand=True)
        self.mesh_study_copy_button = ttk.Button(
            details_row, text="Copy selected mesh settings to Workflow / Meshing",
            command=self._copy_selected_mesh_settings, state="disabled")
        self.mesh_study_copy_button.pack(side="right", padx=(8, 0), anchor="n")
