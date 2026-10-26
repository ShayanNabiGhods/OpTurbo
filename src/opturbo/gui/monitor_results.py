"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import replace
import math

from ..models import VariableSpec
from ..objectives import OBJECTIVES
from ..paths import APPLICATION_ROOT as APP_ROOT
from ..storage import atomic_json
from ..workflows import get_workflow


class MonitorResultsMixin:
    def _record_result(self, event: dict) -> None:
        run_only = bool(event.get("run_only", getattr(
            get_workflow(self.config_model.workflow_id, APP_ROOT), "run_only", False)))
        with self.history_lock:
            optimization_id = event.get("optimization_id")
            already_saved = optimization_id and any(
                row.get("optimization_id") == optimization_id
                and row.get("generation") == event.get("generation")
                and row.get("candidate") == event.get("candidate")
                for row in self.history
            )
            if not already_saved:
                self.history.append(event)
            if self.store:
                if run_only:
                    atomic_json(self.store.root / "run_history.json", {"evaluations": self.history})
                else:
                    self.store.save_history(self.history)
        cp = float(event.get("cp", float("nan")))
        ct_value = event.get("ct")
        ct = float(ct_value) if ct_value is not None else float("nan")
        cp_normalized = self._format_table_value(event.get("cp_normalized"))
        ct_normalized = self._format_table_value(event.get("ct_normalized"))
        status = event.get("status", "completed")
        self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                 event.get("candidate"), self._format_table_value(event.get("tsr")),
                                 f"{cp:.7g}" if math.isfinite(cp) and cp > -1e20 else "—",
                                 f"{ct:.7g}" if math.isfinite(ct) else "—", cp_normalized, ct_normalized, status))
        with self.history_lock:
            progress_value = (sum(1 for row in self.history
                                  if row.get("optimization_id") == event.get("optimization_id"))
                              if event.get("optimization_id") else len(self.history))
        self.progress.configure(value=progress_value)
        fitness = float(event.get("fitness", cp))
        objective = str(event.get("objective", "cp"))
        if run_only:
            if status == "completed":
                self.best_var.set(f"Latest run: Cp: {cp:.7g}    Ct: {ct:.7g}")
            self._refresh_run_tsr_plot()
        elif (status == "completed" and objective == self.config_model.ga.objective
                and fitness > self.best_fitness):
            self.best_fitness = fitness
            self.best_var.set(self._best_result_text(event))
            if self.store:
                atomic_json(self.store.root / "best" / "best_result.json", event)
        self._refresh_plots(event)

    def _best_result_text(self, event: dict | None = None) -> str:
        """Format the best objective and identify its generation and candidate."""
        label = OBJECTIVES.get(self.config_model.ga.objective, "objective")
        if event is None:
            return f"Best {label}: —"
        fitness = float(event.get("fitness", event.get("cp", float("nan"))))
        cp = float(event.get("cp", float("nan")))
        ct_value = event.get("ct")
        ct = float(ct_value) if ct_value is not None else float("nan")
        candidate = event.get("candidate", "—")
        generation = event.get("generation", "—")
        return (f"Best {label}: {fitness:.7g}    Cp: {cp:.7g}    Ct: {ct:.7g}    "
                f"Candidate {candidate}, Generation {generation}")

    @staticmethod
    def _format_table_value(value: object) -> str:
        """Format an optional finite result value for the optimization table."""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return "—"
        return f"{parsed:.7g}" if math.isfinite(parsed) else "—"

    def _refresh_results(self) -> None:
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.best_fitness = float("-inf")
        run_only = bool(getattr(get_workflow(self.config_model.workflow_id, APP_ROOT), "run_only", False))
        for event in self.history:
            cp = float(event.get("cp", float("nan")))
            ct_value = event.get("ct")
            ct = float(ct_value) if ct_value is not None else float("nan")
            self.results_tree.insert("", "end", values=(event.get("evaluation"), event.get("generation"),
                                     event.get("candidate"), self._format_table_value(event.get("tsr")),
                                     f"{cp:.7g}" if math.isfinite(cp) and cp > -1e20 else "—",
                                     f"{ct:.7g}" if math.isfinite(ct) else "—",
                                     self._format_table_value(event.get("cp_normalized")),
                                     self._format_table_value(event.get("ct_normalized")),
                                     event.get("status", "completed")))
            if run_only:
                if event.get("status", "completed") == "completed":
                    self.best_var.set(f"Latest run: Cp: {cp:.7g}    Ct: {ct:.7g}")
                continue
            fitness = float(event.get("fitness", cp))
            objective = str(event.get("objective", "cp"))
            if (event.get("status", "completed") == "completed"
                    and objective == self.config_model.ga.objective
                    and fitness > self.best_fitness):
                self.best_fitness = fitness
                self.best_var.set(self._best_result_text(event))
        self._refresh_plots(self.history[-1] if self.history else {})
        if run_only:
            self._refresh_run_tsr_plot()

    def _refresh_run_tsr_plot(self) -> None:
        """Plot completed open-workflow sweep results against TSR."""
        points = []
        for row in self.history:
            try:
                tsr, cp, ct = float(row["tsr"]), float(row["cp"]), float(row["ct"])
            except (KeyError, TypeError, ValueError):
                continue
            if (row.get("status", "completed") == "completed"
                    and math.isfinite(tsr) and math.isfinite(cp) and math.isfinite(ct)
                    and cp > -1e20):
                points.append((tsr, cp, ct))
        points.sort(key=lambda point: point[0])
        series = [("Cp", [point[1] for point in points]),
                  ("Ct", [point[2] for point in points])]
        if points:
            self.run_tsr_plot.set_series(series, x_values=[point[0] for point in points])
        else:
            self.run_tsr_plot.set_series(series)

    def _refresh_plots(self, latest: dict) -> None:
        cp_values = [float(row.get("cp", row.get("fitness", 0))) for row in self.history if float(row.get("cp", row.get("fitness", -1e30))) > -1e20]
        ct_values = [float(row.get("ct", 0)) for row in self.history if row.get("ct") is not None and str(row.get("ct")) != "nan"]
        cp_normalized = [float(row["cp_normalized"]) for row in self.history
                         if row.get("cp_normalized") is not None and math.isfinite(float(row["cp_normalized"]))]
        ct_normalized = [float(row["ct_normalized"]) for row in self.history
                         if row.get("ct_normalized") is not None and math.isfinite(float(row["ct_normalized"]))]
        self.performance_plot.set_series([("Cp", cp_values), ("Ct", ct_values),
                                          ("Cp normalized", cp_normalized),
                                          ("Ct normalized", ct_normalized)])
        bem_series = []
        loss_label = "Bontempo tip × Prandtl root" if latest.get("tip_loss_model") == "bontempo2025" else "Prandtl tip × root"
        for key, label in (("a", "a"), ("a_prime", "a′"), ("loss_factor", loss_label)):
            values = latest.get(key, latest.get("prandtl_loss") if key == "loss_factor" else None)
            if isinstance(values, list):
                bem_series.append((label, [float(value) for value in values]))
        self.bem_plot.set_series(bem_series)

    def _show_candidate(self, genome: dict[str, float]) -> None:
        """Display the candidate currently passing through the external tools."""
        variables = [VariableSpec(item.key, item.label, genome.get(item.key, item.value),
                                  item.minimum, item.maximum, item.optimize)
                     for item in self.config_model.design_variables]
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(self.config_model.geometry, **geometry_values)
        try:
            top, bottom = self._duct_outline(geometry, variables)
        except Exception:
            return
        self._draw_domain(self.domain_canvas, geometry, top, bottom)
        self._draw_duct(self.duct_canvas, geometry, top, bottom)
