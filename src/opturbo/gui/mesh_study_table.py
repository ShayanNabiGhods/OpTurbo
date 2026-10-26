"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields
import math

from ..models import MeshSettings
from .constants import LABELS


class MeshStudyTableMixin:
    def _refresh_mesh_study_table(self) -> None:
        """Rebuild the mesh-study summary table from persisted candidate rows."""
        if not hasattr(self, "mesh_study_tree"):
            return
        for iid in self.mesh_study_tree.get_children():
            self.mesh_study_tree.delete(iid)
        for index, row in enumerate(self.mesh_study_rows, 1):
            iid = str(row.get("id", index))
            values = (
                row.get("id", index), row.get("status", "unknown"),
                self._format_cell_count(row.get("cell_count")),
                self._format_seconds(row.get("meshing_seconds")),
                self._format_seconds(row.get("fluent_solution_seconds")),
                self._format_seconds(row.get("candidate_seconds")),
                row.get("outer_iterations") if row.get("outer_iterations") is not None else "—",
                self._format_table_value(row.get("cp")), self._format_table_value(row.get("ct")),
                self._format_table_value(row.get("cp_normalized")),
                self._format_table_value(row.get("ct_normalized")),
            )
            self.mesh_study_tree.insert("", "end", iid=iid, values=values)

    @staticmethod
    def _format_cell_count(value: object) -> str:
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def _format_seconds(value: object) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "—"
        return f"{number:.1f}" if math.isfinite(number) else "—"

    def _show_mesh_study_selection(self, _event: object | None = None) -> None:
        """Show selected candidate's full mesh controls and solver summary."""
        selected = self.mesh_study_tree.selection()
        row = next((item for index, item in enumerate(self.mesh_study_rows, 1)
                    if str(item.get("id", index)) in selected), None)
        self.mesh_study_details.configure(state="normal")
        self.mesh_study_details.delete("1.0", "end")
        if row:
            lines = [f"Candidate {row.get('id', '—')} — {row.get('status', 'unknown')}"]
            if row.get("error"):
                lines.append(f"Error: {row['error']}")
            mesh = row.get("mesh_settings", {})
            lines.append("Mesh settings:")
            for item in fields(MeshSettings):
                if item.name == "duct_size_cm" and self._run_only_selected():
                    continue
                value = mesh.get(item.name, "—")
                lines.append(f"  {LABELS.get(item.name, item.name)}: {value}")
            lines.append(f"Candidate folder: {row.get('candidate_dir', '—')}")
            self.mesh_study_details.insert("1.0", "\n".join(lines))
            self.mesh_study_copy_button.configure(state="normal" if mesh else "disabled")
        else:
            self.mesh_study_copy_button.configure(state="disabled")
        self.mesh_study_details.configure(state="disabled")
