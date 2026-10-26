"""Check workflow registration and the geometry-only open-turbine contract."""

import tempfile
import unittest
from pathlib import Path
import sys

from opturbo.models import ProjectConfig
from opturbo.workflows import available_workflows, get_workflow
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.parameters import (
    OUTPUT_NAMES,
    OpenTurbineParameters,
)
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.validation import validate_parameters


class OpenTurbineWorkflowTests(unittest.TestCase):
    """Ensure the new workflow stops at a duct-free STEP handoff."""

    def test_workflow_is_selectable_and_preserves_its_saved_id(self):
        workflow_id = "axisymmetric_2d_open_turbine"
        self.assertIn(workflow_id, available_workflows())
        config = ProjectConfig(workflow_id=workflow_id)
        loaded = ProjectConfig.from_dict(config.to_dict())
        self.assertEqual(loaded.workflow_id, workflow_id)
        self.assertEqual(get_workflow(workflow_id, Path.cwd()).title,
                         "2D axisymmetric open turbine")

    def test_runner_stops_before_fluent_and_exposes_mesh_preparation(self):
        workflow = get_workflow("axisymmetric_2d_open_turbine", Path.cwd())
        runner = workflow.create_runner()
        self.assertTrue(workflow.preparation_only)
        self.assertTrue(hasattr(runner, "generate_assembly"))
        self.assertTrue(hasattr(runner, "generate_mesh"))
        for stage in ("spaceclaim_stage", "cfd_stage"):
            self.assertFalse(hasattr(runner, stage))

    def test_open_mesh_script_uses_no_duct_controls(self):
        workflow = get_workflow("axisymmetric_2d_open_turbine", Path.cwd())
        runner = workflow.create_runner()
        script = runner._mesh_script(ProjectConfig(), OpenTurbineParameters())
        self.assertNotIn("DUCT", script)
        self.assertNotIn("duct-sizing", script)
        self.assertIn("resolution-sizing", script)
        self.assertIn("hub-sizing", script)

    def test_mesh_preparation_requires_manual_spaceclaim_document(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = ProjectConfig()
            config.tools.workbench = sys.executable
            config.tools.handoff_dir = str(root / "handoff")
            runner = get_workflow("axisymmetric_2d_open_turbine", Path.cwd()).create_runner()
            with self.assertRaisesRegex(FileNotFoundError, "Run the open-turbine SpaceClaim script first"):
                runner.generate_mesh(config, root / "candidate")

    def test_open_assembly_contains_no_duct_step(self):
        self.assertEqual(set(OUTPUT_NAMES), {"domain", "resolution", "actuator", "hub", "assembly"})
        self.assertEqual(OUTPUT_NAMES["assembly"], "open_turbine_assembly.step")
        self.assertNotIn("duct", " ".join(OUTPUT_NAMES.values()).lower())

    def test_geometry_validation_and_unique_handoff_directories(self):
        validate_parameters(OpenTurbineParameters())
        with self.assertRaises(ValueError):
            validate_parameters(OpenTurbineParameters(domain_height=100.0))
        runner = get_workflow("axisymmetric_2d_open_turbine", Path.cwd()).create_runner()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = runner._reserve_handoff_folder(root)
            second = runner._reserve_handoff_folder(root)
            self.assertEqual(first.name, "open_turbine_run_001")
            self.assertEqual(second.name, "open_turbine_run_002")
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
