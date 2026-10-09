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

    def test_first_journal_applies_k_omega_setup_once(self):
        from opturbo.cfd.fluent import write_journal
        from types import SimpleNamespace
        import tempfile

        blade = SimpleNamespace(radius=[0.1], dr=[0.1])
        settings = {
            "viscous_model": "k_omega",
            "gradient_scheme": "green_gauss_node_based",
            "pressure_scheme": "presto",
            "momentum_scheme": "quick",
            "swirl_scheme": "third_order_muscl",
            "k_scheme": "first_order_upwind",
            "omega_scheme": "second_order_upwind",
            "pressure_velocity_coupling": "coupled",
            "residual_omega": 2e-5,
        }
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "first.jou"
            later = Path(folder) / "later.jou"
            write_journal(first, blade, True, 1, fluent_settings=settings)
            write_journal(later, blade, False, 2, fluent_settings=settings)
            first_text = first.read_text(encoding="utf-8")
            later_text = later.read_text(encoding="utf-8")
        self.assertIn("/define/models/viscous/kw-standard/yes", first_text)
        self.assertIn("/solve/monitors/residual/convergence-criteria/", first_text)
        self.assertIn("/solve/set/gradient-scheme/yes", first_text)
        self.assertIn("/solve/set/p-v-coupling/24", first_text)
        self.assertIn("/solve/set/discretization-scheme/pressure/14", first_text)
        self.assertIn("/solve/set/discretization-scheme/mom/4", first_text)
        self.assertIn("/solve/set/discretization-scheme/omega/1", first_text)
        self.assertNotIn("/define/models/viscous", later_text)
        self.assertNotIn("/solve/set/discretization-scheme", later_text)

    def test_first_journal_uses_model_specific_equations(self):
        from opturbo.cfd.fluent import first_iteration_setup

        epsilon = "\n".join(first_iteration_setup({"viscous_model": "k_epsilon"}))
        spalart = "\n".join(first_iteration_setup({"viscous_model": "spalart_allmaras"}))
        self.assertIn("/define/models/viscous/ke-standard/yes", epsilon)
        self.assertIn("/solve/set/discretization-scheme/epsilon/1", epsilon)
        self.assertNotIn("/solve/set/discretization-scheme/omega/", epsilon)
        self.assertIn("/define/models/viscous/spalart-allmaras/yes", spalart)
        self.assertIn("/solve/set/discretization-scheme/nut/1", spalart)
        self.assertNotIn("/solve/set/discretization-scheme/epsilon/", spalart)


if __name__ == "__main__":
    unittest.main()
