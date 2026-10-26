"""Focused Tkinter behavior for the OpTurbo application."""

from copy import deepcopy
from pathlib import Path
import queue
from tkinter import messagebox
import uuid

from ..optimizer import GeneticAlgorithm
from ..objectives import OBJECTIVES, objective_value
from ..pipeline.overlap import evaluate_generation
from ..pipeline.failures import failed_candidate
from ..storage import ProjectStore
from .configuration import saved_configuration_matches
from ..paths import APPLICATION_ROOT as APP_ROOT
from ..workflows import get_workflow


class OptimizationWorkerMixin:
    def _single_worker(self) -> None:
        try:
            assert self.store is not None
            candidate = self.store.candidate_dir(0, 1)
            workflow = get_workflow(self.config_model.workflow_id, APP_ROOT)
            if getattr(workflow, "preparation_only", False):
                assembly = self._runner().generate_assembly(self.config_model, candidate)
                self.events.put(("done", f"STEP assembly created: {assembly}"))
                return
            genome = {item.key: item.value for item in self.config_model.design_variables if item.optimize}
            self.events.put(("candidate", {"generation": 0, "candidate": 1, "genome": genome}))
            result = self._runner().evaluate(self.config_model, genome, candidate)
            event = {"evaluation": len(self.history) + 1, "generation": 0, "candidate": 1,
                     "fitness": objective_value(result, self.config_model.ga.objective),
                     "objective": self.config_model.ga.objective, "genome": genome, **result}
            self.events.put(("result", event))
            self.events.put(("done", "Current design evaluation completed"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _open_turbine_mesh_worker(self) -> None:
        """Build the open-turbine mesh from its manually prepared SCDOC."""
        try:
            assert self.store is not None
            candidate = self.store.candidate_dir(0, 1)
            mesh = self._runner().generate_mesh(self.config_model, candidate)
            self.events.put(("done", f"Open-turbine mesh created: {mesh}"))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _ga_worker(self, resume: bool = False) -> None:
        state: dict | None = None
        store: ProjectStore | None = None
        try:
            assert self.store is not None
            config = deepcopy(self.config_model)
            store = self.store
            if resume:
                state = store.load_optimization_state()
                if not state or state.get("status") == "completed":
                    raise RuntimeError("This project has no unfinished optimization to resume.")
                if not saved_configuration_matches(state.get("configuration"), config):
                    raise RuntimeError("Project settings changed since this optimization was started.")
                run_id = str(state["run_id"])
            else:
                run_id = uuid.uuid4().hex
                state = {
                    "run_id": run_id,
                    "status": "running",
                    "configuration": config.to_dict(),
                }
                store.save_optimization_state(state)

            with self.history_lock:
                resume_results = {
                    (int(row["generation"]), int(row["candidate"])): row
                    for row in self.history
                    if row.get("optimization_id") == run_id
                    and int(row.get("generation", 0)) >= 1
                    and "candidate" in row
                }
            optimizer = GeneticAlgorithm(config.design_variables, config.ga)
            runner = self._runner()
            if resume and config.cfd.source_initialization == "previous_candidate":
                completed_rows = [row for row in resume_results.values()
                                  if row.get("status", "completed") == "completed"]
                completed_rows.sort(key=lambda row: int(row.get("evaluation", 0)))
                for row in reversed(completed_rows):
                    candidate_path = row.get("candidate_dir")
                    if candidate_path:
                        source_path = Path(candidate_path) / "04_cfd" / "fluent" / "final_ad_sources.dat"
                        if source_path.is_file():
                            runner.previous_candidate_sources = source_path
                            break

            def evaluate(genome: dict[str, float], generation: int, index: int):
                folder = store.candidate_dir(generation, index)
                self.events.put(("candidate", {"generation": generation, "candidate": index,
                                               "genome": genome.copy()}))
                try:
                    result = runner.evaluate(config, genome, folder)
                    return objective_value(result, config.ga.objective), result
                except Exception as error:
                    failure = failed_candidate(folder, error, config.ga.objective)
                    self.events.put(("log", f"{folder.name}: {failure['status']}; candidate skipped with penalty: {error}"))
                    return failure["fitness"], failure

            def generation_evaluator(candidates, generation):
                return evaluate_generation(runner, config, candidates, generation, store.candidate_dir,
                                           self.stop_requested.is_set,
                                           lambda event: self.events.put(("candidate", event)))

            def on_result(event: dict) -> None:
                key = (int(event["generation"]), int(event["candidate"]))
                if key in resume_results:
                    return
                saved_event = {**event, "optimization_id": run_id}
                with self.history_lock:
                    self.history.append(saved_event)
                    store.save_history(self.history)
                    resume_results[key] = saved_event
                self.events.put(("result", saved_event))

            best = optimizer.run(evaluate, on_result=on_result,
                                 should_stop=self.stop_requested.is_set,
                                 evaluate_generation=generation_evaluator if config.ga.overlap_preparation else None,
                                 resume_results=resume_results)
            if (not self.stop_requested.is_set() and best.result
                    and best.result.get("status") in {"failed", "skipped_fluent_crash"}):
                raise RuntimeError("Every candidate failed; optimization ran through the configured candidates but found no valid result.")
            run_status = "stopped" if self.stop_requested.is_set() else "finished"
            state_data = store.load_optimization_state() or {}
            state_data.update({
                "run_id": run_id,
                "status": "stopped" if self.stop_requested.is_set() else "completed",
                "configuration": config.to_dict(),
                "completed_candidates": len(resume_results),
            })
            store.save_optimization_state(state_data)
            label = OBJECTIVES[config.ga.objective]
            self.events.put(("done", f"Optimization {run_status}. Best {label} = {best.fitness:.6g}"))
        except Exception as error:
            if store is not None and state is not None:
                state["status"] = "interrupted"
                state["last_error"] = str(error)
                store.save_optimization_state(state)
            self.events.put(("error", str(error)))

    def _stop(self) -> None:
        self.stop_requested.set()
        self.status_var.set("Stop requested — waiting for the current candidate")
        self._append_log("Stop requested. Active CFD and any overlapping preparation will finish safely. No further CFD candidate will start.")

    def _terminate(self) -> None:
        """Cancel scheduling and kill active external process trees without deleting results."""
        self.stop_requested.set()
        self.terminate_requested.set()
        self.status_var.set("Terminating active processes; partial results will be retained")

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "candidate":
                    candidate = payload  # type: ignore[assignment]
                    self.status_var.set(
                        f"Evaluating generation {candidate['generation']}, candidate {candidate['candidate']}")
                    self._show_candidate(candidate["genome"])
                elif kind == "result":
                    self._record_result(payload)  # type: ignore[arg-type]
                elif kind == "mesh_study_result":
                    row = payload  # type: ignore[assignment]
                    self.mesh_study_rows.append(row)
                    self._refresh_mesh_study_table()
                    self.mesh_study_tree.selection_set(str(row["id"]))
                    self.mesh_study_tree.see(str(row["id"]))
                    self._show_mesh_study_selection()
                elif kind == "mesh_study_progress":
                    self.mesh_study_progress.configure(value=int(payload))
                elif kind == "done":
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                    self._set_running(False)
                elif kind == "error":
                    self.status_var.set("Run failed")
                    self._append_log("ERROR: " + str(payload))
                    self._set_running(False)
                    messagebox.showerror("OpTurbo run failed", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)
