"""Focused Tkinter behavior for the OpTurbo application."""

import tkinter as tk
from tkinter import messagebox, ttk

from .pdf_help import open_guide


class LayoutMixin:
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
            "About OpTurbo", "OpTurbo V0.3.1\nDAWT design and performance analysis"))
        help_menu.add_command(label="Theory Guide (PDF)", command=lambda: open_guide("theory.pdf"))
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, text="OpTurbo", style="Title.TLabel").pack(side="left")
        self.workflow_summary_label = ttk.Label(
            header, text="Geometry → SpaceClaim → Mesh → CFD/BEM → Genetic optimization",
            style="Subtitle.TLabel")
        self.workflow_summary_label.pack(side="left", padx=16, pady=(6, 0))
        self.status_var = tk.StringVar(value="Ready — choose a project folder to begin")
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="right")
        ttk.Button(header, text="Help", command=lambda: open_guide("manual.pdf")).pack(
            side="right", padx=(0, 10))
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._build_project_tab()
        self._build_design_tab()
        self._build_workflow_tab()
        self._build_simple_bem_tab()
        self._build_mesh_study_tab()
        self._build_optimization_tab()
        self._build_monitor_tab()
        self._build_accessibility_tab()
