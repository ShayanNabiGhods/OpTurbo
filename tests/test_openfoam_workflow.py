"""Checks for OpenFOAM workflow selection, case generation, and result readers."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opturbo.models import ProjectConfig
from opturbo.workflows import available_workflows, get_workflow
from opturbo.workflows.axisymmetric_2d.cfd.resources import load_blade, load_setup
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.parameters import (
    OUTPUT_NAMES,
    OpenTurbineParameters,
)
from opturbo.workflows.axisymmetric_2d_open_turbine_openfoam.case import (
    radial_zone_edges,
    write_block_mesh_dict,
    write_case_fields,
    write_fv_models,
    write_system_dictionaries,
    write_topo_set_dict,
)
from opturbo.workflows.axisymmetric_2d_open_turbine_openfoam.runner import (
    SURFACE_NAME,
    SURFACE_PROFILE_NAME,
    OpenFoamOpenTurbineRunner,
    windows_path_to_wsl,
)


APP_ROOT = Path(__file__).parents[1]
WORKFLOW_ID = "axisymmetric_2d_open_turbine_openfoam"
TABLES = APP_ROOT / "resources" / "workflows" / WORKFLOW_ID / "cfd_tables"


class OpenFoamWorkflowTests(unittest.TestCase):
    """Keep the new OpenFOAM route independently selectable and reproducible."""

    def test_workflow_registration_and_old_project_defaults(self):
        self.assertIn(WORKFLOW_ID, available_workflows())
        workflow = get_workflow(WORKFLOW_ID, APP_ROOT)
        config = ProjectConfig(workflow_id=WORKFLOW_ID)
        loaded = ProjectConfig.from_dict(config.to_dict())
        self.assertEqual(loaded.openfoam, config.openfoam)
        self.assertTrue(workflow.run_only)
        self.assertEqual(workflow.title, "2D axisymmetric open turbine (OpenFOAM)")
        self.assertEqual(type(workflow.create_runner()).__name__, "OpenFoamOpenTurbineRunner")
        # Projects saved before the OpenFOAM option existed still load with defaults.
        old = config.to_dict()
        old.pop("openfoam")
        self.assertEqual(ProjectConfig.from_dict(old).openfoam.max_global_cells, 2_000_000)

    def test_wsl_path_conversion_handles_spaces_and_drive_letters(self):
        self.assertEqual(
            windows_path_to_wsl(r"C:\Project Saves\Run 1\case", "/mnt"),
            "/mnt/c/Project Saves/Run 1/case",
        )
        self.assertEqual(windows_path_to_wsl(r"E:\Results\case", "/windows"),
                         "/windows/e/Results/case")
        self.assertEqual(windows_path_to_wsl("/home/user/case"), "/home/user/case")

    def test_openfoam_scratch_case_uses_a_space_free_wsl_path(self):
        config = ProjectConfig(workflow_id=WORKFLOW_ID)
        runner = get_workflow(WORKFLOW_ID, APP_ROOT).create_runner()
        scratch = runner._new_wsl_case(config)
        self.assertTrue(scratch.startswith(config.tools.wsl_work_root + "/run_"))
        self.assertNotIn(" ", scratch)
        config.tools.wsl_work_root = "/tmp/OpenFOAM Runs"
        with self.assertRaisesRegex(ValueError, "without spaces"):
            runner._new_wsl_case(config)

    def test_openfoam_geometry_launch_exports_the_hub_surface(self):
        config = ProjectConfig(workflow_id=WORKFLOW_ID)
        runner = get_workflow(WORKFLOW_ID, APP_ROOT).create_runner()
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder) / "candidate"

            def fake_run(command, _cwd, _log, _emit, _cancel):
                output = Path(command[command.index("--out") + 1])
                output.mkdir(parents=True, exist_ok=True)
                for name in OUTPUT_NAMES.values():
                    (output / name).write_text("mock STEP", encoding="utf-8")
                (output / SURFACE_NAME).write_text("solid hub\nendsolid hub\n", encoding="ascii")
                (output / SURFACE_PROFILE_NAME).write_text(
                    json.dumps({"units": "m", "points": [[0, 0], [1, 1], [2, 0]]}),
                    encoding="utf-8",
                )

            with patch("opturbo.workflows.axisymmetric_2d_open_turbine_openfoam.runner.require_executable",
                       return_value="freecadcmd.exe"), patch(
                "opturbo.workflows.axisymmetric_2d_open_turbine_openfoam.runner.run_streaming",
                side_effect=fake_run,
            ):
                assembly = runner.generate_assembly(config, candidate)

            self.assertTrue(assembly.is_file())
            self.assertTrue((candidate / "01_geometry" / SURFACE_NAME).is_file())
            self.assertTrue((candidate / "candidate.json").is_file())
            self.assertEqual(json.loads((candidate / "candidate.json").read_text())["workflow_id"], WORKFLOW_ID)

    def test_case_writer_generates_wedge_mesh_rans_fields_and_source_zones(self):
        config = ProjectConfig(workflow_id=WORKFLOW_ID)
        geometry = OpenTurbineParameters()
        blade = load_blade(TABLES, stations=4,
                           thickness=geometry.actuator_thickness / 1000)
        _flow, turbine = load_setup(TABLES)
        edges = radial_zone_edges(blade, turbine)
        self.assertEqual(len(edges), len(blade.radius) + 1)
        self.assertTrue(all(right > left for left, right in zip(edges, edges[1:])))

        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder) / "case"
            system = case / "system"
            constant = case / "constant"
            system.mkdir(parents=True)
            constant.mkdir(parents=True)
            x0 = (geometry.hub_origin_x - geometry.hub_length / 2) / 1000
            x1 = (geometry.hub_origin_x + geometry.hub_length / 2) / 1000
            radius = geometry.hub_radius / 1000
            profile = [[x0, 0.0], [x0 + radius, radius],
                       [x1 - radius, radius], [x1, 0.0]]
            nx, nr = write_block_mesh_dict(system / "blockMeshDict", geometry,
                                           config.mesh, config.openfoam, profile)
            self.assertGreater(nx, 0)
            self.assertGreater(nr, 0)
            block = (system / "blockMeshDict").read_text(encoding="utf-8")
            self.assertIn("type wedge", block)
            self.assertIn("blocks", block)
            self.assertIn("axisCore", block)
            self.assertIn("type wall", block)
            write_case_fields(case, geometry, config.cfd, config.openfoam,
                              config.cfd.viscous_model)
            write_system_dictionaries(case, config.cfd, config.openfoam,
                                      config.cfd.viscous_model, blade,
                                      geometry.actuator_origin_x / 1000)
            write_topo_set_dict(system / "topoSetDict", edges, geometry, config.cfd)
            write_fv_models(constant / "fvModels", [100.0] * len(blade.radius),
                            [-10.0] * len(blade.radius), config.cfd.density_kg_m3)

            self.assertTrue((case / "constant" / "momentumTransport").is_file())
            self.assertTrue((case / "0" / "U").is_file())
            self.assertTrue((case / "0" / "epsilon").is_file())
            self.assertIn("rotorBand000", (system / "topoSetDict").read_text(encoding="utf-8"))
            models = (constant / "fvModels").read_text(encoding="utf-8")
            self.assertIn("type semiImplicitSource", models)
            self.assertIn("volumeMode specific", models)
            self.assertIn("explicit (84.245", models)
            control = (system / "controlDict").read_text(encoding="utf-8")
            self.assertIn("application simpleFoam", control)
            self.assertIn("actuatorDisk", control)
            self.assertIn("writeControl writeTime", control)

    def test_probe_reader_and_cellzone_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            case = Path(folder) / "case"
            probes = case / "postProcessing" / "actuatorDisk" / "120"
            probes.mkdir(parents=True)
            (probes / "U").write_text(
                "# Probe 0 (0.01 0.05 0)\n"
                "# Time\n"
                "10 (9 0 0.1) (8.5 0 0.2)\n",
                encoding="utf-8",
            )
            self.assertEqual(OpenFoamOpenTurbineRunner._read_probes(case, 2),
                             [(9.0, 0.0, 0.1), (8.5, 0.0, 0.2)])
            zones = case / "cellZones"
            zones.write_text(
                "rotorBand000 { type cellZone; cellLabels List<label> 12 ( ); }\n"
                "rotorBand001 { type cellZone; cellLabels List<label> 9 ( ); }\n",
                encoding="utf-8",
            )
            self.assertEqual(OpenFoamOpenTurbineRunner._zone_counts(zones),
                             {"rotorBand000": 12, "rotorBand001": 9})

    def test_mesh_cell_count_parser_ignores_quality_summary_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "checkMesh.log"
            log.write_text(
                "    cells: 46950\n"
                "    Concave cells found, number of cells: 2342\n",
                encoding="utf-8",
            )
            self.assertEqual(OpenFoamOpenTurbineRunner._cell_count(log), 46950)
            log.write_text("Mesh OK.\n", encoding="utf-8")
            OpenFoamOpenTurbineRunner._validate_mesh_quality(log)
            log.write_text("Failed 4 mesh checks.\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "4 failed checks"):
                OpenFoamOpenTurbineRunner._validate_mesh_quality(log)


if __name__ == "__main__":
    unittest.main()
