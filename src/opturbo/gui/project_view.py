"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..models import ProjectConfig, ToolPaths
from ..paths import APPLICATION_ROOT as APP_ROOT
from ..storage import ProjectStore
from ..workflows import available_workflows, get_workflow
from .widgets import ScrollableFrame
from .pdf_help import add_pdf_help_button


class ProjectViewMixin:
    def _build_project_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="  Project  ")
        tab.columnconfigure(0, weight=1, uniform="project_columns")
        tab.columnconfigure(1, weight=1, uniform="project_columns")
        tab.rowconfigure(0, weight=1)
        left_scroll = ScrollableFrame(tab)
        right_scroll = ScrollableFrame(tab)
        left_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right_scroll.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        left, right = left_scroll.body, right_scroll.body
        project_box = ttk.LabelFrame(left, text="Workflow project", padding=12)
        project_box.pack(fill="x")
        ttk.Label(project_box, text="Engineering workflow").grid(row=0, column=0, sticky="w", pady=5)
        add_pdf_help_button(project_box, 0, "workflow", "Engineering workflow")
        self.workflow_id_var = tk.StringVar(value=self.config_model.workflow_id)
        workflow_choices = {
            workflow_id: get_workflow(workflow_id, APP_ROOT).title
            for workflow_id in available_workflows()
        }
        self.workflow_label_to_id = {label: workflow_id for workflow_id, label in workflow_choices.items()}
        self.workflow_label_var = tk.StringVar(value=workflow_choices[self.config_model.workflow_id])
        workflow_combo = ttk.Combobox(
            project_box,
            textvariable=self.workflow_label_var,
            values=tuple(workflow_choices.values()),
            state="readonly",
        )
        workflow_combo.grid(row=0, column=1, sticky="ew", padx=8)
        workflow_combo.bind("<<ComboboxSelected>>", self._select_workflow)
        ttk.Label(project_box, text="Project name").grid(row=1, column=0, sticky="w", pady=5)
        add_pdf_help_button(project_box, 1, "project_name", "Project name")
        self.project_name_var = tk.StringVar()
        ttk.Entry(project_box, textvariable=self.project_name_var).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Label(project_box, text="Save folder").grid(row=2, column=0, sticky="w", pady=5)
        add_pdf_help_button(project_box, 2, "save_folder", "Save folder")
        self.save_dir_var = tk.StringVar()
        ttk.Entry(project_box, textvariable=self.save_dir_var, state="readonly").grid(row=2, column=1, sticky="ew", padx=8)
        ttk.Button(project_box, text="Choose…", command=self._choose_project_folder).grid(row=2, column=3)
        ttk.Button(project_box, text="Save now", command=self._save_project).grid(row=3, column=1, sticky="w", padx=8, pady=8)
        project_box.columnconfigure(1, weight=1)
        tools = ttk.LabelFrame(right, text="Installed engineering tools", padding=12)
        tools.pack(fill="both", expand=True)
        self._add_dataclass_form(tools, "tools", ToolPaths, browse_paths=True)
        note = ("SpaceClaim handoff is intentionally fixed at C:\\OpTurbo\\Temp Files. "
                "The application stages files there and copies all results into the selected workflow folder.")
        ttk.Label(left, text=note, style="Subtitle.TLabel", wraplength=480,
                  justify="left").pack(fill="x", pady=14)

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
            if self._save_project():
                self._load_mesh_study_project_state()

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
                self.best_var.set(self._best_result_text())
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

    def _load_model_into_fields(self) -> None:
        self.project_name_var.set(self.config_model.project_name)
        self.save_dir_var.set(self.config_model.save_dir)
        self.workflow_id_var.set(self.config_model.workflow_id)
        self.workflow_label_var.set(get_workflow(self.config_model.workflow_id, APP_ROOT).title)
        for section in ("tools", "geometry", "mesh", "cfd", "ga"):
            settings = getattr(self.config_model, section)
            for item in fields(settings):
                variable = self.field_vars[(section, item.name)]
                value = getattr(settings, item.name)
                if section == "mesh" and item.name == "cpu_cores":
                    value = "Program Controlled" if value is None else str(value)
                elif section == "mesh" and item.name == "method" and value == "Default":
                    value = "Default (ANSYS automatic)"
                elif isinstance(value, float):
                    value = self._format_user_number(value)
                variable.set(value)
        self.design_type_var.set(self.config_model.geometry.design_type)
        self.theme_var.set(self.config_model.accessibility.theme)
        self.text_scale_var.set(str(self.config_model.accessibility.text_scale))
        self.high_contrast_var.set(self.config_model.accessibility.high_contrast)
        self.accent_var.set(self.config_model.accessibility.accent_color)
        self.candidate_marker_size_var.set(str(self.config_model.accessibility.candidate_marker_size))
        self.outer_marker_size_var.set(str(self.config_model.accessibility.outer_marker_size))
        self.table_row_spacing_var.set(str(self.config_model.accessibility.table_row_spacing))
        if hasattr(self, "best_var"):
            self.best_var.set(self._best_result_text())
        self.design_variable_sets = {self.config_model.geometry.design_type: self.config_model.design_variables[:]}
        self._make_parsec_rows()
        self._load_mesh_study_project_state()
        self._apply_accessibility()
        self._draw_design()

    def _select_workflow(self, _event: object | None = None) -> None:
        """Store the selected workflow ID while showing its readable title."""
        self.workflow_id_var.set(self.workflow_label_to_id[self.workflow_label_var.get()])
