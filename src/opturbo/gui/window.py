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
