"""Check the open-turbine run pipeline and its packaged engineering resources."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from opturbo.models import ProjectConfig
from opturbo.storage import atomic_json
from opturbo.workflows import available_workflows, get_workflow
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.parameters import (
    OUTPUT_NAMES,
    OpenTurbineParameters,
)
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.validation import validate_parameters
from opturbo.workflows.axisymmetric_2d_open_turbine.runner import OpenTurbineRunner
from opturbo.pipeline.process import windows_path


APP_ROOT = Path(__file__).parents[1]
WORKFLOW_RESOURCES = APP_ROOT / "resources" / "workflows" / "axisymmetric_2d_open_turbine"


class OpenTurbineWorkflowTests(unittest.TestCase):
    """Ensure open-turbine evaluation stays duct-free and project-local."""

    def test_workflow_is_selectable_and_run_only(self):
        workflow_id = "axisymmetric_2d_open_turbine"
        self.assertIn(workflow_id, available_workflows())
        config = ProjectConfig(workflow_id=workflow_id)
        loaded = ProjectConfig.from_dict(config.to_dict())
        self.assertEqual(loaded.workflow_id, workflow_id)
        workflow = get_workflow(workflow_id, APP_ROOT)
        self.assertEqual(workflow.title, "2D axisymmetric open turbine")
        self.assertTrue(workflow.run_only)

    def test_runner_has_full_run_and_mesh_study_interfaces(self):
        runner = get_workflow("axisymmetric_2d_open_turbine", APP_ROOT).create_runner()
        self.assertTrue(runner.run_only)
        for method in ("evaluate", "prepare_mesh_study_geometry", "evaluate_mesh_study_candidate"):
            self.assertTrue(callable(getattr(runner, method)))

    def test_packaged_mesh_script_uses_no_duct_controls(self):
        runner = get_workflow("axisymmetric_2d_open_turbine", APP_ROOT).create_runner()
        script = runner._mesh_script(
            ProjectConfig(), OpenTurbineParameters(),
            WORKFLOW_RESOURCES / "meshing" / "mesh_script.py")
        self.assertNotIn("DUCT", script)
        self.assertNotIn("duct-sizing", script)
        self.assertIn("resolution-sizing", script)
        self.assertIn("hub-sizing", script)

    def test_spaceclaim_package_paths_are_localized_to_candidate(self):
        source = WORKFLOW_RESOURCES / "spaceclaim" / "open_turbine_assembly.scscript"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assembly = root / "01_geometry" / "open_turbine_assembly.step"
            scdoc = root / "02_spaceclaim" / "open_turbine_assembly.scdoc"
            scdoc.parent.mkdir(parents=True)
            destination = root / "02_spaceclaim" / source.name
            OpenTurbineRunner._rewrite_spaceclaim_package(source, destination, assembly, scdoc)
            with ZipFile(destination) as archive:
                script = archive.read("_script").decode("utf-8")
        self.assertIn(windows_path(assembly), script)
        self.assertIn(windows_path(scdoc), script)
        self.assertNotIn(r"C:\OpTurbo\Temp Files\open_turbine_assembly", script)

    def test_open_fluent_case_is_packaged_and_shared_stage_uses_it(self):
        case = WORKFLOW_RESOURCES / "fluent" / "open_turbine_assembly.cas.h5"
        self.assertTrue(case.is_file())
        runner = get_workflow("axisymmetric_2d_open_turbine", APP_ROOT).create_runner()
        runner.cfd_stage = Mock()
        mesh = Path("candidate/03_mesh/open_turbine_assembly.msh")
        output = Path("candidate/04_cfd")
        config = ProjectConfig()
        config.cfd.source_initialization = "previous_candidate"
        config.cfd.previous_source_weight = 0.4
        runner._cfd(config, mesh, output)
        runner.cfd_stage.run.assert_called_once()
        args, kwargs = runner.cfd_stage.run.call_args
        self.assertEqual(args[0].cfd.source_initialization, "conservative")
        self.assertEqual(args[0].cfd.previous_source_weight, 1.0)
        self.assertEqual(config.cfd.source_initialization, "previous_candidate")
        self.assertEqual(config.cfd.previous_source_weight, 0.4)
        self.assertEqual(args[1:], (mesh, output))
        self.assertEqual(kwargs["baseline_case"], case)
        self.assertEqual(kwargs["case_name"], case.name)

    def test_workflow_resource_trees_are_independent_and_complete(self):
        ducted = get_workflow("axisymmetric_2d", APP_ROOT).resources
        opened = get_workflow("axisymmetric_2d_open_turbine", APP_ROOT).resources
        for resource in ("meshing/extract_mesh_artifact.py", "fluent/ad_sources.c",
                         "fluent/libudf/src/ad_sources.c", "cfd_tables/ntnu_geometry.csv",
                         "cfd_tables/s826_alpha.csv"):
            with self.subTest(resource=resource):
                self.assertTrue((ducted / resource).is_file())
                self.assertTrue((opened / resource).is_file())
                self.assertNotEqual((ducted / resource).resolve(), (opened / resource).resolve())
        self.assertTrue((ducted / "spaceclaim/profile_assembly.scscript").is_file())
        self.assertTrue((opened / "spaceclaim/open_turbine_assembly.scscript").is_file())

    def test_run_saves_all_stages_under_a_fresh_project_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder) / "candidates" / "generation_000" / "candidate_001_run02"
            runner = get_workflow("axisymmetric_2d_open_turbine", APP_ROOT).create_runner()

            def geometry(_config, candidate_dir):
                directory = candidate_dir / "01_geometry"
                directory.mkdir(parents=True)
                step = directory / "open_turbine_assembly.step"
                step.write_text("test geometry", encoding="utf-8")
                atomic_json(candidate_dir / "candidate.json",
                            runner._candidate_metadata(_config, runner._geometry_parameters(_config)))
                return step

            def spaceclaim(_config, _assembly, output):
                output.mkdir(parents=True)
                result = output / "open_turbine_assembly.scdoc"
                result.write_text("test CAD", encoding="utf-8")
                return result

            def mesh(_config, _scdoc, output):
                output.mkdir(parents=True)
                result = output / "open_turbine_assembly.msh"
                result.write_text("test mesh", encoding="utf-8")
                return result

            runner.generate_assembly = geometry
            runner._spaceclaim = spaceclaim
            runner._mesh = mesh
            runner._cfd = lambda _config, _mesh, output: (
                output.mkdir(parents=True), {"cp": 0.42, "ct": 0.81}
            )[1]
            with patch.object(OpenTurbineRunner, "_validate_settings"):
                result = runner.evaluate(ProjectConfig(), candidate)

            self.assertEqual(result["status"], "completed")
            self.assertEqual((result["cp"], result["ct"]), (0.42, 0.81))
            for stage in ("01_geometry", "02_spaceclaim", "03_mesh", "04_cfd"):
                self.assertTrue((candidate / stage).is_dir())
            self.assertTrue((candidate / "candidate.json").is_file())
            self.assertTrue((candidate / "result.json").is_file())
            saved_configuration = json.loads(
                (candidate / "candidate.json").read_text(encoding="utf-8"))["configuration"]
            self.assertNotIn("ga", saved_configuration)
            self.assertNotIn("design_variables", saved_configuration)
            self.assertFalse(any(name.startswith("duct_")
                                 for name in saved_configuration["geometry"]))
            self.assertNotIn("duct_size_cm", saved_configuration["mesh"])
            self.assertNotIn("handoff_dir", saved_configuration["tools"])
            self.assertFalse((Path(folder) / "Temp Files").exists())

    def test_open_assembly_contains_no_duct_step(self):
        self.assertEqual(set(OUTPUT_NAMES), {"domain", "resolution", "actuator", "hub", "assembly"})
        self.assertEqual(OUTPUT_NAMES["assembly"], "open_turbine_assembly.step")
        self.assertNotIn("duct", " ".join(OUTPUT_NAMES.values()).lower())

    def test_geometry_validation(self):
        validate_parameters(OpenTurbineParameters())
        with self.assertRaises(ValueError):
            validate_parameters(OpenTurbineParameters(domain_height=100.0))


if __name__ == "__main__":
    unittest.main()
