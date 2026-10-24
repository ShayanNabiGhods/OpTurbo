"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import asdict, replace
import json
from pathlib import Path
import uuid

from ..models import MeshSettings, ProjectConfig
from ..storage import atomic_json


class MeshStudyWorkerMixin:
    def _mesh_study_worker(
        self, config: ProjectConfig, candidates: list[MeshSettings], enabled: dict[str, bool],
        run_id: str | None = None,
    ) -> None:
        """Run each mesh/Fluent case against one shared geometry document."""
        state_path = self._mesh_study_state_path()
        state = self._read_mesh_study_run_state() or {}
        try:
            assert self.store is not None
            study_root = self.store.root / "mesh_study"
            history_path = study_root / "history.json"
            study_root.mkdir(parents=True, exist_ok=True)
            try:
                saved_rows = json.loads(history_path.read_text(encoding="utf-8")).get("candidates", [])
            except (OSError, TypeError, ValueError):
                saved_rows = []
            records = list(saved_rows) if isinstance(saved_rows, list) else []
            next_id = max((int(row.get("id", 0)) for row in records), default=0) + 1
            run_id = run_id or str(state.get("run_id") or uuid.uuid4().hex)
            completed_numbers = {int(row.get("candidate_number", 0)) for row in records
                                 if row.get("run_id") == run_id and row.get("status") == "completed"}
            progress_count = len(completed_numbers)
            state.update({"run_id": run_id, "status": "running"})
            if state_path is not None:
                atomic_json(state_path, state)
            run_root = study_root / "runs" / run_id
            runner = self._runner()
            if config.cfd.source_initialization == "previous_candidate":
                for previous in reversed(records):
                    if previous.get("status") != "completed":
                        continue
                    candidate_path = previous.get("candidate_dir")
                    if candidate_path:
                        source_path = Path(candidate_path) / "04_cfd" / "fluent" / "final_ad_sources.dat"
                        if source_path.is_file():
                            runner.previous_candidate_sources = source_path
                            break
            prepared_config, scdoc = runner.prepare_mesh_study_geometry(config, run_root / "shared_geometry")
            for index, mesh_settings in enumerate(candidates, 1):
                if self.stop_requested.is_set():
                    break
                if index in completed_numbers:
                    continue
                candidate_folder = run_root / f"mesh_{index:03d}"
                attempt = 2
                while candidate_folder.exists():
                    candidate_folder = run_root / f"mesh_{index:03d}_attempt{attempt:02d}"
                    attempt += 1
                candidate_config = replace(prepared_config, mesh=mesh_settings)
                record = {
                    "id": next_id,
                    "run_id": run_id,
                    "candidate_number": index,
                    "status": "failed",
                    "mesh_settings": asdict(mesh_settings),
                    "enabled_mesh_variables": [name for name, is_enabled in enabled.items() if is_enabled],
                    "candidate_dir": str(candidate_folder),
                }
                self.events.put(("log", f"Mesh study candidate {next_id}: meshing and CFD/BEM evaluation starting"))
                try:
                    result = runner.evaluate_mesh_study_candidate(candidate_config, scdoc, candidate_folder)
                    record.update({
                        "status": "completed",
                        "cell_count": result.get("cell_count"),
                        "meshing_seconds": result.get("meshing_seconds"),
                        "fluent_solution_seconds": result.get("fluent_solution_seconds"),
                        "candidate_seconds": result.get("candidate_seconds"),
                        "outer_iterations": result.get("outer_iterations"),
                        "cp": result.get("cp"),
                        "ct": result.get("ct"),
                        "cp_normalized": result.get("cp_normalized"),
                        "ct_normalized": result.get("ct_normalized"),
                    })
                except Exception as error:
                    record["error"] = str(error)
                    record.update(getattr(error, "mesh_study_metrics", {}))
                    self.events.put(("log", f"Mesh study candidate {next_id} failed: {error}"))
                records.append(record)
                atomic_json(history_path, {"candidates": records})
                self.events.put(("mesh_study_result", record))
                progress_count += 1
                self.events.put(("mesh_study_progress", progress_count))
                next_id += 1
            message = ("Mesh study stopped after the active case." if self.stop_requested.is_set()
                       else "Mesh study completed.")
            state["status"] = "stopped" if self.stop_requested.is_set() else "completed"
            if state_path is not None:
                atomic_json(state_path, state)
            self.events.put(("done", message))
        except Exception as error:
            state["status"] = "interrupted"
            state["last_error"] = str(error)
            if state_path is not None:
                atomic_json(state_path, state)
            self.events.put(("error", f"Mesh study could not continue: {error}"))
