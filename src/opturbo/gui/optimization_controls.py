"""Focused Tkinter behavior for the OpTurbo application."""

import threading
from tkinter import messagebox
from typing import Callable

from ..pipeline import PipelineRunner
from ..paths import APPLICATION_ROOT as APP_ROOT
from .configuration import saved_configuration_matches
from ..workflows import get_workflow


class OptimizationControlsMixin:
    def _run_only_selected(self) -> bool:
        """Return whether the selected workflow supports evaluation without GA."""
        workflow_id = (self.workflow_id_var.get() if hasattr(self, "workflow_id_var")
                       else self.config_model.workflow_id)
        return bool(getattr(get_workflow(workflow_id, APP_ROOT), "run_only", False))

    def _apply_workflow_mode(self, running: bool = False) -> None:
        """Expose controls supported by the selected workflow's implemented stages."""
        run_only = self._run_only_selected()
        if hasattr(self, "design_tab"):
            self.notebook.tab(self.design_tab, state="hidden" if run_only else "normal")
        if hasattr(self, "mesh_study_tab"):
            self.notebook.tab(self.mesh_study_tab, state="normal")
        if hasattr(self, "workflow_pages"):
            self.workflow_pages.tab(self.mesh_settings_page, state="normal")
            self.workflow_pages.tab(self.cfd_settings_page, state="normal")
        setting_controls = getattr(self, "setting_controls", {})
        for (section, name), controls in setting_controls.items():
            is_hidden_for_open_workflow = (
                (section == "geometry" and
                 (name.startswith("duct_") or name == "design_type")) or
                (section == "mesh" and name == "duct_size_cm") or
                (section == "tools" and name == "handoff_dir") or
                (section == "cfd" and name in {
                    "source_initialization", "previous_source_weight"})
            )
            if not is_hidden_for_open_workflow:
                continue
            for control in controls:
                if run_only:
                    control.grid_remove()
                else:
                    control.grid()
        source_initialization = getattr(self, "field_vars", {}).get(
            ("cfd", "source_initialization"))
        if source_initialization is not None:
            if run_only:
                if not hasattr(self, "_saved_source_initialization"):
                    self._saved_source_initialization = source_initialization.get()
                source_initialization.set("conservative")
            elif hasattr(self, "_saved_source_initialization"):
                source_initialization.set(self._saved_source_initialization)
                del self._saved_source_initialization
            if hasattr(self, "_refresh_source_weight_control"):
                self._refresh_source_weight_control()
        if hasattr(self, "hub_duct_settings_group"):
            self.hub_duct_settings_group.configure(
                text="Hub placement" if run_only else "Hub and duct placement")
        self.notebook.tab(self.optimization_tab, text="  Run  " if run_only else "  Optimization  ")
        if hasattr(self, "performance_plot"):
            self.performance_plot.title = "Run performance history" if run_only else "Optimization objective history"
            self.performance_plot.redraw()
        if hasattr(self, "monitor_plots"):
            self.monitor_plots.tab(0, text="Run history" if run_only else "Candidates")
        if hasattr(self, "run_only_note"):
            if run_only:
                self.run_only_note.grid()
                self.ga_settings_frame.grid_remove()
                self.ga_actions.pack_forget()
                self.single_button.configure(text="Run performance evaluation")
                self.results_title.configure(text="Performance evaluation results")
                self.results_tree.configure(displaycolumns=self.run_only_columns)
                self.best_var.set("Latest run: Cp: —    Ct: —")
            else:
                self.run_only_note.grid_remove()
                self.ga_settings_frame.grid()
                self.ga_actions.pack(fill="x")
                self.single_button.configure(text="Evaluate current design")
                self.results_title.configure(text="Optimization progress")
                self.results_tree.configure(displaycolumns=self.results_tree["columns"])
                self.best_var.set(self._best_result_text())
        if hasattr(self, "single_button"):
            self.single_button.configure(state="disabled" if running else "normal")
            self.start_button.configure(state="disabled" if running or run_only else "normal")
            self.resume_button.configure(state="disabled" if running or run_only else "normal")
        if hasattr(self, "mesh_study_manual_button"):
            state = "disabled" if running else "normal"
            self.mesh_study_manual_button.configure(state=state)
            self.mesh_study_auto_button.configure(state=state)
        if hasattr(self, "mesh_study_description"):
            self._apply_mesh_study_workflow_mode(run_only)
        if hasattr(self, "workflow_summary_label"):
            summary = ("FreeCAD → SpaceClaim → Mesh → Fluent/BEM evaluation" if run_only else
                       "Geometry → SpaceClaim → Mesh → CFD/BEM → Genetic optimization")
            self.workflow_summary_label.configure(text=summary)
        if hasattr(self, "workflow_note_label"):
            note = (
                "Each run saves geometry, SpaceClaim, mesh, and Fluent/BEM results in a "
                "new candidate folder in the selected project. No run files are written "
                "under C:\\OpTurbo\\Temp Files. Mesh study remains available."
                if run_only else
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
            study_state = "disabled" if running else "normal"
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
                                     and not self._run_only_selected() else "disabled")

    def _run_single(self) -> None:
        if not self._require_saved_project():
            return
        status = ("Running open-turbine performance evaluation" if self._run_only_selected()
                  else "Evaluating current design")
        self._start_worker(self._single_worker, status)

    def _run_ga(self) -> None:
        self._start_ga(resume=False)

    def _resume_ga(self) -> None:
        self._start_ga(resume=True)

    def _start_ga(self, resume: bool) -> None:
        if self._run_only_selected():
            messagebox.showinfo("Run workflow", "The open-turbine workflow supports single-run performance evaluations and mesh studies, not genetic optimization.")
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
