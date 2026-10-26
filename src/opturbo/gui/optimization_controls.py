"""Focused Tkinter behavior for the OpTurbo application."""

import threading
from tkinter import messagebox
from typing import Callable

from ..pipeline import PipelineRunner
from ..paths import APPLICATION_ROOT as APP_ROOT
from .configuration import saved_configuration_matches
from ..workflows import get_workflow


class OptimizationControlsMixin:
    def _preparation_only_selected(self) -> bool:
        """Return whether the selected workflow stops before Fluent solving."""
        workflow_id = (self.workflow_id_var.get() if hasattr(self, "workflow_id_var")
                       else self.config_model.workflow_id)
        return bool(getattr(get_workflow(workflow_id, APP_ROOT), "preparation_only", False))

    def _apply_workflow_mode(self, running: bool = False) -> None:
        """Expose controls supported by the selected workflow's implemented stages."""
        preparation_only = self._preparation_only_selected()
        if hasattr(self, "design_tab"):
            self.notebook.tab(self.design_tab, state="disabled" if preparation_only else "normal")
        if hasattr(self, "mesh_study_tab"):
            self.notebook.tab(self.mesh_study_tab, state="disabled" if preparation_only else "normal")
        if hasattr(self, "workflow_pages"):
            self.workflow_pages.tab(self.mesh_settings_page, state="normal")
            self.workflow_pages.tab(self.cfd_settings_page, state="disabled" if preparation_only else "normal")
        for name in ("duct_origin_x", "duct_origin_r", "duct_points"):
            controls = getattr(self, "setting_controls", {}).get(("geometry", name), ())
            for control in controls:
                if preparation_only:
                    control.grid_remove()
                else:
                    control.grid()
        mesh_duct_controls = getattr(self, "setting_controls", {}).get(("mesh", "duct_size_cm"), ())
        for control in mesh_duct_controls:
            if preparation_only:
                control.grid_remove()
            else:
                control.grid()
        if hasattr(self, "hub_duct_settings_group"):
            self.hub_duct_settings_group.configure(
                text="Hub placement" if preparation_only else "Hub and duct placement")
        if hasattr(self, "single_button"):
            self.single_button.configure(
                text="Generate STEP assembly" if preparation_only else "Evaluate current design",
                state="disabled" if running else "normal",
            )
            self.start_button.configure(state="disabled" if running or preparation_only else "normal")
            self.resume_button.configure(state="disabled" if running or preparation_only else "normal")
        if hasattr(self, "mesh_button"):
            if preparation_only:
                self.mesh_button.pack(fill="x", pady=3, after=self.single_button)
                self.mesh_button.configure(state="disabled" if running else "normal")
            else:
                self.mesh_button.pack_forget()
        if hasattr(self, "mesh_study_manual_button"):
            state = "disabled" if running or preparation_only else "normal"
            self.mesh_study_manual_button.configure(state=state)
            self.mesh_study_auto_button.configure(state=state)
        if hasattr(self, "workflow_summary_label"):
            summary = ("FreeCAD → Manual SpaceClaim → ANSYS Meshing → Fluent case handoff" if preparation_only else
                       "Geometry → SpaceClaim → Mesh → CFD/BEM → Genetic optimization")
            self.workflow_summary_label.configure(text=summary)
        if hasattr(self, "workflow_note_label"):
            note = (
                "Open-turbine mode creates the axisymmetric domain, resolution region, "
                "actuator disk, and hub without a duct. Run your SpaceClaim script against "
                "C:\\OpTurbo\\Temp Files\\open_turbine_assembly.step; then click Generate "
                "open-turbine mesh. The mesh uses the app settings without duct sizing and "
                "is saved in a unique folder under C:\\OpTurbo\\Temp Files. Fluent is not run."
                if preparation_only else
                "SpaceClaim handoff is intentionally fixed at C:\\OpTurbo\\Temp Files. "
                "The application stages files there and copies all results into the selected workflow folder."
            )
            self.workflow_note_label.configure(text=note)

    def _set_running(self, running: bool) -> None:
        self._apply_workflow_mode(running)
        self._update_resume_button(running)
        self._update_mesh_study_resume_button(running)
        self.stop_button.configure(state="normal" if running else "disabled")
        self.terminate_button.configure(state="normal" if running else "disabled")
        if hasattr(self, "mesh_study_manual_button"):
            study_state = "disabled" if running or self._preparation_only_selected() else "normal"
            self.mesh_study_manual_button.configure(state=study_state)
            self.mesh_study_auto_button.configure(state=study_state)
            study_running = running and self.active_task == "mesh_study"
            self.mesh_study_stop_button.configure(state="normal" if study_running else "disabled")
            self.mesh_study_terminate_button.configure(state="normal" if study_running else "disabled")
        if not running:
            self.active_task = None

    def _update_resume_button(self, running: bool = False) -> None:
        """Enable resume when the selected project has an unfinished GA run."""
        if not hasattr(self, "resume_button"):
            return
        resumable = False
        if self.store is not None:
            try:
                state = self.store.load_optimization_state()
                resumable = bool(state and state.get("status") != "completed")
            except (OSError, ValueError, TypeError):
                resumable = False
        self.resume_button.configure(state="normal" if resumable and not running
                                     and not self._preparation_only_selected() else "disabled")

    def _run_single(self) -> None:
        if not self._require_saved_project():
            return
        status = ("Generating open-turbine STEP assembly" if self._preparation_only_selected()
                  else "Evaluating current design")
        self._start_worker(self._single_worker, status)

    def _run_open_turbine_mesh(self) -> None:
        """Run ANSYS Meshing on the manually generated open-turbine SCDOC."""
        if not self._preparation_only_selected():
            return
        if not self._require_saved_project():
            return
        self._start_worker(self._open_turbine_mesh_worker, "Generating open-turbine mesh")

    def _run_ga(self) -> None:
        self._start_ga(resume=False)

    def _resume_ga(self) -> None:
        self._start_ga(resume=True)

    def _start_ga(self, resume: bool) -> None:
        if self._preparation_only_selected():
            messagebox.showinfo("Preparation workflow", "This workflow prepares geometry and mesh; Fluent solving is not configured yet.")
            return
        if resume:
            if self.store is None:
                messagebox.showerror("No project selected", "Open the project that contains the optimization to resume.")
                return
            try:
                requested_config = self._read_model_from_fields()
                state = self.store.load_optimization_state()
            except Exception as error:
                messagebox.showerror("Cannot resume optimization", str(error))
                return
            if not state or state.get("status") == "completed":
                messagebox.showerror("No resumable optimization", "This project has no unfinished optimization to resume.")
                self._update_resume_button()
                return
            if not saved_configuration_matches(state.get("configuration"), requested_config):
                messagebox.showerror(
                    "Settings changed",
                    "The project settings differ from the saved optimization. Restore the original settings before resuming.",
                )
                return
            if not self._save_project():
                return
        elif not self._require_saved_project():
            return
        if not any(item.optimize for item in self.config_model.design_variables):
            messagebox.showerror("No variables selected", "Tick at least one variable in the Design tab.")
            return
        assert self.store is not None
        state = self.store.load_optimization_state()
        if resume:
            assert state is not None
        elif state and state.get("status") != "completed":
            if not messagebox.askyesno(
                "Start a new optimization?",
                "This project has an unfinished optimization. Starting a new run will replace its resume point. Continue?",
            ):
                return
        total = (self.config_model.ga.population_size +
                 (self.config_model.ga.generations - 1) *
                 (self.config_model.ga.population_size - self.config_model.ga.elite_count))
        completed = 0
        if resume and state:
            run_id = state.get("run_id")
            completed = sum(1 for row in self.history if row.get("optimization_id") == run_id)
        self.progress.configure(maximum=total, value=completed)
        self._start_worker(lambda: self._ga_worker(resume=resume),
                           "Resuming optimization" if resume else "Optimization running")

    def _start_worker(self, target: Callable[[], None], status: str, task: str = "optimization") -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_requested.clear()
        self.terminate_requested.clear()
        self.active_task = task
        self._set_running(True)
        self.status_var.set(status)
        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _runner(self) -> PipelineRunner:
        workflow = get_workflow(self.config_model.workflow_id, APP_ROOT)
        return workflow.create_runner(
            lambda line: self.events.put(("log", line)),
            self.terminate_requested.is_set,
        )
