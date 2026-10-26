"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import asdict, replace
from copy import deepcopy
import json
from pathlib import Path
from tkinter import messagebox
import uuid

from ..models import MeshSettings, ProjectConfig
from ..workflows.axisymmetric_2d.mesh_study import automatic_mesh_settings
from ..storage import atomic_json
from .constants import MESH_STUDY_SIZE_FIELDS
from .configuration import saved_configuration_matches


class MeshStudyRunMixin:
    def _require_saved_project(self) -> bool:
        if not self._save_project():
            return False
        return self.store is not None

    def _start_manual_mesh_study(self) -> None:
        """Run the currently entered mesh setup once for the selected design."""
        try:
            config = self._read_model_from_fields()
            panel_mesh = self._read_mesh_study_settings()
            enabled = self._get_mesh_study_enabled()
            mesh = self._mesh_settings_with_enabled_values(config.mesh, panel_mesh, enabled)
            config = replace(config, mesh=mesh)
            self._validate_positive_settings(config)
            if not self._save_project():
                return
            config = replace(deepcopy(self.config_model), mesh=mesh)
            self._save_mesh_study_form(panel_mesh, enabled)
            self._begin_mesh_study(config, [mesh], enabled, "Running mesh study candidate")
        except Exception as error:
            messagebox.showerror("Cannot start mesh study", str(error))

    def _start_automatic_mesh_study(self) -> None:
        """Run a baseline, mesh-control screening, and space-filling sweep."""
        try:
            config = self._read_model_from_fields()
            panel_mesh = self._read_mesh_study_settings()
            enabled = self._get_mesh_study_enabled()
            base_mesh = self._mesh_settings_with_enabled_values(config.mesh, panel_mesh, enabled)
            count = int(self.mesh_study_count_var.get())
            if not 1 <= count <= 100:
                raise ValueError("Automatic sweep cases must be between 1 and 100.")
            enabled_sizes = {name for name, is_enabled in enabled.items() if is_enabled}
            if not base_mesh.inflation_enabled:
                enabled_sizes.difference_update({"inflation_layers", "inflation_max_thickness_cm"})
            if not enabled_sizes:
                raise ValueError("Enable at least one active mesh size variable for an automatic sweep.")
            bounds = self._read_mesh_study_bounds(enabled_sizes)
            config = replace(config, mesh=base_mesh)
            self._validate_positive_settings(config)
            candidates = automatic_mesh_settings(base_mesh, count, base_mesh.method,
                                                 enabled_fields=enabled_sizes, bounds=bounds,
                                                 strategy=("even" if self.mesh_study_strategy_var.get() == "Evenly spaced"
                                                           else "screening"))
            if not self._save_project():
                return
            config = replace(deepcopy(self.config_model), mesh=base_mesh)
            self._save_mesh_study_form(panel_mesh, enabled)
            self._begin_mesh_study(config, candidates, enabled,
                                   f"Running automatic mesh sweep ({len(candidates)} cases)")
        except Exception as error:
            messagebox.showerror("Cannot start mesh study", str(error))

    def _mesh_study_state_path(self) -> Path | None:
        return self.store.root / "mesh_study" / "run_state.json" if self.store is not None else None

    def _begin_mesh_study(self, config: ProjectConfig, candidates: list[MeshSettings],
                          enabled: dict[str, bool], status: str) -> None:
        """Save a reproducible candidate plan before starting a new mesh study."""
        state_path = self._mesh_study_state_path()
        if state_path is None:
            raise RuntimeError("Save a workflow project before starting a mesh study.")
        previous = self._read_mesh_study_run_state()
        if previous and previous.get("status") != "completed":
            if not messagebox.askyesno(
                    "Replace unfinished mesh study?",
                    "This project has an unfinished mesh study. Starting a new study will replace its resume point. Continue?"):
                return
        run_id = uuid.uuid4().hex
        state = {
            "run_id": run_id,
            "status": "running",
            "configuration": config.to_dict(),
            "candidates": [asdict(candidate) for candidate in candidates],
            "enabled_variables": enabled,
            "sweep_strategy": self.mesh_study_strategy_var.get(),
        }
        atomic_json(state_path, state)
        self.mesh_study_progress.configure(maximum=len(candidates), value=0)
        self._start_worker(lambda: self._mesh_study_worker(config, candidates, enabled, run_id),
                           status, task="mesh_study")

    def _read_mesh_study_run_state(self) -> dict | None:
        path = self._mesh_study_state_path()
        if path is None or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _resume_mesh_study(self) -> None:
        """Continue an unfinished saved mesh study, skipping completed cases."""
        if self.store is None:
            messagebox.showerror("No project selected", "Open the project containing the mesh study to resume.")
            return
        try:
            state = self._read_mesh_study_run_state()
            if not state or state.get("status") == "completed":
                messagebox.showerror("No resumable mesh study", "This project has no unfinished mesh study to resume.")
                self._update_mesh_study_resume_button()
                return
            saved_config = ProjectConfig.from_dict(state["configuration"])
            requested_config = replace(self._read_model_from_fields(), mesh=saved_config.mesh)
            if not saved_configuration_matches(state.get("configuration"), requested_config):
                messagebox.showerror(
                    "Settings changed",
                    "The workflow settings differ from the saved mesh study. Restore the original settings before resuming.",
                )
                return
            candidates = [MeshSettings(**item) for item in state["candidates"]]
            enabled = {name: bool(value) for name, value in state.get("enabled_variables", {}).items()}
            saved_strategy = state.get("sweep_strategy", "Screening + combinations")
            if saved_strategy in {"Screening + combinations", "Evenly spaced"}:
                self.mesh_study_strategy_var.set(saved_strategy)
            if not candidates:
                raise ValueError("The saved mesh study contains no candidate settings.")
            history_path = self.store.root / "mesh_study" / "history.json"
            try:
                rows = json.loads(history_path.read_text(encoding="utf-8")).get("candidates", [])
            except (OSError, TypeError, ValueError):
                rows = []
            run_id = str(state["run_id"])
            completed = {int(row.get("candidate_number", 0)) for row in rows
                         if row.get("run_id") == run_id and row.get("status") == "completed"}
            state["status"] = "running"
            atomic_json(self._mesh_study_state_path(), state)
            self.mesh_study_progress.configure(maximum=len(candidates), value=len(completed))
            self._start_worker(lambda: self._mesh_study_worker(saved_config, candidates, enabled, run_id),
                               f"Resuming mesh study ({len(completed)}/{len(candidates)} complete)",
                               task="mesh_study")
        except Exception as error:
            messagebox.showerror("Cannot resume mesh study", str(error))

    def _save_mesh_study_form(self, settings: MeshSettings, enabled: dict[str, bool]) -> None:
        """Persist the isolated mesh-study form values in the selected project."""
        if self.store is not None:
            mesh_settings = asdict(settings)
            if self._run_only_selected():
                mesh_settings.pop("duct_size_cm", None)
            atomic_json(self.store.root / "mesh_study" / "settings.json", {
                "mesh_settings": mesh_settings, "enabled_variables": enabled,
                "sweep_strategy": self.mesh_study_strategy_var.get(),
                "variable_bounds": {
                    name: {"minimum": self.mesh_study_min_vars[name].get(),
                           "maximum": self.mesh_study_max_vars[name].get()}
                    for name in MESH_STUDY_SIZE_FIELDS
                    if name != "duct_size_cm" or not self._run_only_selected()
                },
            })
