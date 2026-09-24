"""Tests for generated Workbench handoff instructions."""

import unittest
from pathlib import Path
import zipfile

from opturbo.pipeline.runner import PipelineRunner


class PipelineTests(unittest.TestCase):
    def test_workbench_journal_contains_candidate_paths(self):
        journal = PipelineRunner._workbench_journal(
            Path("/mnt/c/work/design.scdoc"), Path("/mnt/c/work/mesh.py"), Path("/mnt/c/work/project.wbpj"))
        self.assertIn("design.scdoc", journal)
        self.assertIn("mesh.py", journal)
        self.assertIn("project.wbpj", journal)
        self.assertIn("Interactive=False", journal)

    def test_protected_spaceclaim_contract_is_unchanged(self):
        script = Path(__file__).parents[1] / "resources" / "spaceclaim" / "profile_assembly.scscript"
        with zipfile.ZipFile(script) as archive:
            source = archive.read("_script").decode("utf-8")
        self.assertIn(r"C:\OpTurbo\Temp Files\profile_assembly.step", source)
        self.assertIn(r"C:\OpTurbo\Temp Files\profile_assembly.scdoc", source)

    def test_fluent_journal_uses_mesh_replace_command(self):
        from opturbo.cfd.fluent import write_journal
        from types import SimpleNamespace
        import tempfile

        blade = SimpleNamespace(radius=[0.1, 0.2], dr=[0.1, 0.1])
        with tempfile.TemporaryDirectory() as folder:
            journal = Path(folder) / "run.jou"
            write_journal(journal, blade, True, 1)
            text = journal.read_text(encoding="utf-8")
        self.assertIn('/mesh/replace "axisymmetric_mesh.msh"', text)
        self.assertNotIn("/file/replace-mesh", text)
        self.assertIn("facet-avg (line-01 line-02 ) axial-velocity", text)
        self.assertIn("facet-avg (line-01 line-02 ) swirl-velocity", text)
        self.assertNotIn("facet-avg (13 14 )", text)


if __name__ == "__main__":
    unittest.main()
