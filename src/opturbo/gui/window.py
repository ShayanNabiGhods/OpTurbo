"""Tk root window assembled from focused view and workflow mixins."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..models import AccessibilitySettings, ProjectConfig, VariableSpec
from ..storage import ProjectStore
from .accessibility_view import AccessibilityViewMixin
from .appearance import AppearanceMixin
from .config_editor import ConfigEditorMixin
from .design_form import DesignFormMixin
from .design_preview import DesignPreviewMixin
from .duct_preview import DuctPreviewMixin
from .layout import LayoutMixin
from .mesh_study_run import MeshStudyRunMixin
from .mesh_study_settings import MeshStudySettingsMixin
from .mesh_study_table import MeshStudyTableMixin
from .mesh_study_view import MeshStudyViewMixin
from .mesh_study_worker import MeshStudyWorkerMixin
from .monitor_view import MonitorViewMixin
from .monitor_results import MonitorResultsMixin
from .optimization_controls import OptimizationControlsMixin
from .optimization_view import OptimizationViewMixin
from .optimization_worker import OptimizationWorkerMixin
from .project_view import ProjectViewMixin
from .settings_form import SettingsFormMixin
from .workflow_settings import WorkflowSettingsMixin


class OpTurboWindow(
    tk.Tk,
    AppearanceMixin,
    AccessibilityViewMixin,
    ProjectViewMixin,
    SettingsFormMixin,
    WorkflowSettingsMixin,
    ConfigEditorMixin,
    DesignFormMixin,
    DesignPreviewMixin,
    DuctPreviewMixin,
    MeshStudyViewMixin,
    MeshStudySettingsMixin,
    MeshStudyRunMixin,
    MeshStudyWorkerMixin,
    MeshStudyTableMixin,
    OptimizationViewMixin,
    OptimizationControlsMixin,
    OptimizationWorkerMixin,
    MonitorViewMixin,
    MonitorResultsMixin,
    LayoutMixin,
):
    """Compose the application views and initialize their shared state."""

    def __init__(self):
        super().__init__()
        self.numeric_entry_validate = (self.register(self._validate_numeric_entry), "%P")
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
        self.mesh_study_rows: list[dict] = []
        self.mesh_study_vars: dict[str, tk.StringVar] = {}
        self.mesh_study_controls: dict[str, ttk.Widget] = {}
        self.mesh_study_bound_controls: dict[str, tuple[ttk.Widget, ttk.Widget]] = {}
        self.mesh_study_labels: dict[str, ttk.Label] = {}
        self.mesh_study_enabled: dict[str, tk.BooleanVar] = {}
        self.mesh_study_min_vars: dict[str, tk.StringVar] = {}
        self.mesh_study_max_vars: dict[str, tk.StringVar] = {}
        self.active_task: str | None = None
        self.history_lock = threading.Lock()
        self.best_fitness = float("-inf")
        self.field_vars: dict[tuple[str, str], tk.Variable] = {}
        self.inflation_dependent_controls: list[ttk.Widget] = []
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
        self._build_mesh_study_tab()
        self._build_optimization_tab()
        self._build_monitor_tab()
        self._build_accessibility_tab()
