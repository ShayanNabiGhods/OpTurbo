"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import asdict, fields
import json
import math
from tkinter import messagebox

from ..models import MeshSettings
from ..workflows.axisymmetric_2d.mesh_study import mesh_variable_bounds
from .constants import LABELS, MESH_STUDY_SIZE_FIELDS


class MeshStudySettingsMixin:
    def _get_mesh_study_enabled(self) -> dict[str, bool]:
        enabled = {name: variable.get() for name, variable in self.mesh_study_enabled.items()}
        if getattr(self, "_run_only_selected", lambda: False)():
            enabled["duct_size_cm"] = False
        return enabled

    def _refresh_mesh_study_controls(self) -> None:
        """Disable and visually gray mesh controls excluded from the study."""
        for name, widget in self.mesh_study_controls.items():
            is_enabled = self.mesh_study_enabled[name].get() if name in self.mesh_study_enabled else True
            widget.configure(state=("readonly" if name in {"method", "cpu_cores"} else "normal")
                             if is_enabled else "disabled")
            self.mesh_study_labels[name].configure(
                foreground=self.palette["text"] if is_enabled else self.palette["muted"])
            for bound_control in self.mesh_study_bound_controls.get(name, ()):
                bound_control.configure(state="normal" if is_enabled else "disabled")

    def _apply_mesh_study_workflow_mode(self, run_only: bool) -> None:
        """Hide duct sizing and normalized duct metrics for the open workflow."""
        name = "duct_size_cm"
        widgets = [self.mesh_study_checks.get(name), self.mesh_study_labels.get(name),
                   self.mesh_study_controls.get(name),
                   *self.mesh_study_bound_controls.get(name, ())]
        for widget in widgets:
            if widget is None:
                continue
            if run_only:
                widget.grid_remove()
            else:
                widget.grid()
        if run_only:
            if not hasattr(self, "_saved_duct_mesh_enabled"):
                self._saved_duct_mesh_enabled = self.mesh_study_enabled[name].get()
            self.mesh_study_enabled[name].set(False)
        elif hasattr(self, "_saved_duct_mesh_enabled"):
            self.mesh_study_enabled[name].set(self._saved_duct_mesh_enabled)
            del self._saved_duct_mesh_enabled
        self._refresh_mesh_study_controls()
        if hasattr(self, "mesh_study_description"):
            description = (
                "Compare mesh settings for one open-turbine design. Each candidate runs "
                "mesh generation and Fluent/BEM evaluation; results are saved with the project."
                if run_only else
                "Compare mesh settings for one design. Geometry and CFD/BEM settings come from Workflow Settings; "
                "only the mesh settings below vary. Candidate time is mesh plus Fluent/BEM time."
            )
            self.mesh_study_description.configure(text=description)
        if hasattr(self, "mesh_study_tree"):
            columns = self.mesh_study_tree["columns"]
            self.mesh_study_tree.configure(
                displaycolumns=("id", "status", "cells", "mesh_s", "fluent_s", "total_s", "outer", "cp", "ct")
                if run_only else columns
            )

    def _resize_mesh_study_columns(self, event: object) -> None:
        """Distribute mesh-study table columns across its available width."""
        width = max(1, event.width - 4)
        weights = (0.48, 0.72, 0.9, 0.8, 1.05, 0.85, 0.58, 0.72, 0.72, 0.92, 0.92)
        total_weight = sum(weights)
        columns = self.mesh_study_tree["columns"]
        for name, weight in zip(columns, weights):
            self.mesh_study_tree.column(name, width=max(36, round(width * weight / total_weight)), stretch=False)

    @staticmethod
    def _mesh_settings_with_enabled_values(
        workflow_settings: MeshSettings, panel_settings: MeshSettings, enabled: dict[str, bool],
    ) -> MeshSettings:
        """Use panel values for enabled controls and workflow values for disabled ones."""
        values = asdict(workflow_settings)
        for item in fields(MeshSettings):
            if item.name in {"method", "cpu_cores"} or enabled.get(item.name, False):
                values[item.name] = getattr(panel_settings, item.name)
        return MeshSettings(**values)

    def _set_mesh_study_form(
        self, settings: MeshSettings, enabled: dict[str, bool] | None = None,
        bounds: dict[str, tuple[object, object]] | None = None,
    ) -> None:
        """Display one mesh configuration in the mesh-study controls."""
        for item in fields(MeshSettings):
            value = getattr(settings, item.name)
            if item.name == "method" and value == "Default":
                value = "Default (ANSYS automatic)"
            elif item.name == "cpu_cores" and value is None:
                value = "Program Controlled"
            if item.name not in self.mesh_study_vars:
                continue
            self.mesh_study_vars[item.name].set(
                self._format_user_number(value) if isinstance(value, float) else str(value))
            if enabled is not None and item.name in enabled:
                self.mesh_study_enabled[item.name].set(enabled.get(item.name, True))
        if bounds is not None:
            for name, (minimum, maximum) in bounds.items():
                if name in self.mesh_study_min_vars:
                    self.mesh_study_min_vars[name].set(self._format_user_number(minimum))
                    self.mesh_study_max_vars[name].set(self._format_user_number(maximum))
        self._refresh_mesh_study_controls()

    def _load_mesh_study_project_state(self) -> None:
        """Load saved mesh-study cases and per-project study controls."""
        settings = self.config_model.mesh
        bounds = None
        enabled = {name: True for name in MESH_STUDY_SIZE_FIELDS}
        rows = []
        if self.store is not None:
            study_root = self.store.root / "mesh_study"
            settings_path = study_root / "settings.json"
            history_path = study_root / "history.json"
            try:
                if settings_path.is_file():
                    payload = json.loads(settings_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and "mesh_settings" in payload:
                        settings = MeshSettings(**payload["mesh_settings"])
                        saved_enabled = payload.get("enabled_variables", {})
                        enabled.update({name: bool(value) for name, value in saved_enabled.items()
                                        if name in enabled})
                        saved_bounds = payload.get("variable_bounds", {})
                        bounds = mesh_variable_bounds(settings)
                        for name, bound in saved_bounds.items():
                            if name not in bounds:
                                continue
                            if isinstance(bound, dict):
                                bounds[name] = (bound.get("minimum", bounds[name][0]),
                                                bound.get("maximum", bounds[name][1]))
                            elif isinstance(bound, (list, tuple)) and len(bound) == 2:
                                bounds[name] = (bound[0], bound[1])
                    else:
                        # Accept settings files created before per-variable toggles existed.
                        settings = MeshSettings(**payload)
            except (OSError, TypeError, ValueError):
                settings = self.config_model.mesh
                bounds = None
            try:
                if history_path.is_file():
                    rows = json.loads(history_path.read_text(encoding="utf-8")).get("candidates", [])
            except (OSError, TypeError, ValueError):
                rows = []
        self.mesh_study_rows = rows if isinstance(rows, list) else []
        if bounds is None:
            bounds = mesh_variable_bounds(settings)
        self._set_mesh_study_form(settings, enabled, bounds)
        self._refresh_mesh_study_table()
        self._update_mesh_study_resume_button()

    def _update_mesh_study_resume_button(self, running: bool = False) -> None:
        """Enable resume only when this project has an unfinished saved study."""
        button = getattr(self, "mesh_study_resume_button", None)
        if button is None:
            return
        state = self._read_mesh_study_run_state()
        resumable = bool(state and state.get("status") != "completed")
        button.configure(state="normal" if resumable and not running else "disabled")

    def _copy_selected_mesh_settings(self) -> None:
        """Copy the selected candidate's mesh controls into Workflow Settings."""
        selected = self.mesh_study_tree.selection()
        row = next((item for index, item in enumerate(self.mesh_study_rows, 1)
                    if str(item.get("id", index)) in selected), None)
        if not row or not row.get("mesh_settings"):
            return
        for name, value in row["mesh_settings"].items():
            if name == "duct_size_cm" and self._run_only_selected():
                continue
            if ("mesh", name) in self.field_vars:
                if name == "method" and value == "Default":
                    value = "Default (ANSYS automatic)"
                elif name == "cpu_cores" and value is None:
                    value = "Program Controlled"
                self.field_vars[("mesh", name)].set(value)
                self.mesh_study_vars[name].set(
                    self._format_user_number(value) if isinstance(value, float) else str(value))
        self.notebook.select(self.workflow_tab)
        self.workflow_pages.select(self.mesh_settings_page)
        self.status_var.set("Selected mesh controls copied to Workflow Settings; save the project to keep them.")

    def _load_mesh_study_values_from_workflow(self) -> None:
        """Refresh the study controls from current Workflow Settings fields."""
        try:
            config = self._read_model_from_fields()
            self._set_mesh_study_form(config.mesh)
            self.status_var.set("Mesh study controls loaded from Workflow Settings")
        except Exception as error:
            messagebox.showerror("Cannot load mesh settings", str(error))

    def _read_mesh_study_settings(self) -> MeshSettings:
        """Parse the isolated mesh-study controls into a validated dataclass."""
        values = {}
        defaults = MeshSettings()
        for item in fields(MeshSettings):
            if item.name not in self.mesh_study_vars:
                raw = self.field_vars[("mesh", item.name)].get()
            else:
                raw = self.mesh_study_vars[item.name].get()
            default = getattr(defaults, item.name)
            if item.name == "method":
                values[item.name] = "Default" if raw == "Default (ANSYS automatic)" else raw
            elif item.name == "cpu_cores":
                values[item.name] = None if raw == "Program Controlled" else int(raw)
            elif isinstance(default, bool):
                values[item.name] = bool(raw)
            elif isinstance(default, int):
                values[item.name] = int(raw)
            elif isinstance(default, float):
                values[item.name] = float(raw)
            else:
                values[item.name] = str(raw)
        return MeshSettings(**values)

    def _read_mesh_study_bounds(
        self, names: set[str] | None = None,
    ) -> dict[str, tuple[float | int, float | int]]:
        """Parse and validate the user-entered automatic-sweep ranges."""
        bounds: dict[str, tuple[float | int, float | int]] = {}
        for name in (MESH_STUDY_SIZE_FIELDS if names is None else names):
            minimum_raw = self.mesh_study_min_vars[name].get().strip()
            maximum_raw = self.mesh_study_max_vars[name].get().strip()
            try:
                if name == "inflation_layers":
                    minimum, maximum = int(minimum_raw), int(maximum_raw)
                else:
                    minimum, maximum = float(minimum_raw), float(maximum_raw)
            except ValueError as error:
                label = LABELS.get(name, name.replace("_", " "))
                raise ValueError(f"Enter numeric minimum and maximum values for {label}.") from error
            if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum >= maximum:
                label = LABELS.get(name, name.replace("_", " "))
                raise ValueError(f"{label}: minimum must be finite and less than maximum.")
            if name == "growth_rate":
                if minimum <= 1.0:
                    raise ValueError("Growth rate minimum must be greater than 1.0.")
            elif minimum <= 0:
                label = LABELS.get(name, name.replace("_", " "))
                raise ValueError(f"{label}: minimum must be greater than zero.")
            bounds[name] = (minimum, maximum)
        return bounds
