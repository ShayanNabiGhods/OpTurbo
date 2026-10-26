"""Candidate pipeline for open-turbine CFD/BEM evaluation and mesh studies."""

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable
from zipfile import ZIP_DEFLATED, ZipFile

from ...models import ProjectConfig
from ...paths import APPLICATION_ROOT
from ...pipeline.process import require_executable, run_streaming, windows_path
from ...storage import atomic_json
from ..axisymmetric_2d.mesh_study import mesh_cell_count
from ..axisymmetric_2d.pipeline.adapters.fluent import FluentBEMStage
from ..axisymmetric_2d.pipeline.adapters.meshing import AnsysMeshingStage
from .geometry.parameters import OUTPUT_NAMES, OpenTurbineParameters
from .geometry.validation import validate_parameters


class OpenTurbineRunner:
    """Run FreeCAD, SpaceClaim, ANSYS Meshing, and Fluent/BEM per candidate."""

    run_only = True

    def __init__(self, application_root: Path, emit: Callable[[str], None] = print,
                 cancel: Callable[[], bool] | None = None):
        self.root = Path(application_root)
        self.resources = self.root / "resources"
        self.workflow_resources = self.resources / "workflows" / "axisymmetric_2d_open_turbine"
        self.emit = emit
        self.cancel = cancel
        self.cfd_stage = FluentBEMStage(self)

    @staticmethod
    def _geometry_parameters(config: ProjectConfig) -> OpenTurbineParameters:
        """Read only the domain and rotor geometry used by the open workflow."""
        parameters = OpenTurbineParameters(**{
            name: getattr(config.geometry, name)
            for name in OpenTurbineParameters.__dataclass_fields__
        })
        validate_parameters(parameters)
        return parameters

    def generate_assembly(self, config: ProjectConfig, candidate_dir: Path) -> Path:
        """Export the five open-turbine STEP files into a fresh candidate."""
        geometry = self._geometry_parameters(config)
        candidate_dir = Path(candidate_dir)
        self._require_empty_candidate(candidate_dir)
        geometry_dir = candidate_dir / "01_geometry"
        geometry_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(geometry_dir / "open_turbine_settings.json", asdict(geometry))
        worker = (self.root / "src" / "opturbo" / "workflows"
                  / "axisymmetric_2d_open_turbine" / "geometry_worker.py")
        command = [sys.executable, str(worker), "--config",
                   str(geometry_dir / "open_turbine_settings.json"), "--out", str(geometry_dir),
                   "--freecad", require_executable(config.tools.freecad, "FreeCAD")]
        self.emit("[1/4] Generating open-turbine STEP geometry with FreeCAD")
        run_streaming(command, self.root, geometry_dir / "freecad.log", self.emit, self.cancel)
        missing = [name for name in OUTPUT_NAMES.values() if not (geometry_dir / name).is_file()]
        if missing:
            raise FileNotFoundError("FreeCAD did not create required STEP files: " + ", ".join(missing))
        atomic_json(candidate_dir / "candidate.json", self._candidate_metadata(config, geometry))
        return geometry_dir / OUTPUT_NAMES["assembly"]

    def evaluate(self, config: ProjectConfig, candidate_dir: Path) -> dict:
        """Run all four stages and persist raw open-turbine Cp/Ct results."""
        candidate_dir = Path(candidate_dir)
        self._require_empty_candidate(candidate_dir)
        try:
            self._validate_settings(config)
            self._validate_resources()
            assembly = self.generate_assembly(config, candidate_dir)
            scdoc = self._spaceclaim(config, assembly, candidate_dir / "02_spaceclaim")
            mesh = self._mesh(config, scdoc, candidate_dir / "03_mesh")
            atomic_json(candidate_dir / "preparation.json", {"status": "prepared", "mesh": str(mesh)})
            result = self._cfd(config, mesh, candidate_dir / "04_cfd")
            cp, ct = float(result["cp"]), float(result["ct"])
            if not math.isfinite(cp) or not math.isfinite(ct):
                raise ValueError("CFD returned non-finite Cp or Ct values.")
            result.update({
                "status": "completed",
                "workflow_id": "axisymmetric_2d_open_turbine",
                "candidate_dir": str(candidate_dir),
                "mesh": str(mesh),
                "scdoc": str(scdoc),
            })
            atomic_json(candidate_dir / "result.json", result)
            self.emit(f"Open-turbine performance evaluation completed: Cp={cp:.7g}, Ct={ct:.7g}")
            return result
        except Exception as error:
            atomic_json(candidate_dir / "failure.json", {
                "status": "failed",
                "workflow_id": "axisymmetric_2d_open_turbine",
                "candidate_dir": str(candidate_dir),
                "error": str(error),
            })
            raise

    def _spaceclaim(self, config: ProjectConfig, assembly: Path, output: Path) -> Path:
        """Run the packaged SpaceClaim script with candidate-local file paths."""
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        source_script = self.workflow_resources / "spaceclaim" / "open_turbine_assembly.scscript"
        script = output / source_script.name
        scdoc = output / "open_turbine_assembly.scdoc"
        self._rewrite_spaceclaim_package(source_script, script, assembly, scdoc)
        command = [require_executable(config.tools.spaceclaim, "SpaceClaim"), "/Headless=True",
                   f"/RunScript={windows_path(script)}", "/ExitAfterScript=True"]
        self.emit("[2/4] Running the open-turbine SpaceClaim script")
        run_streaming(command, self.root, output / "spaceclaim.log", self.emit, self.cancel)
        if not scdoc.is_file():
            raise FileNotFoundError("SpaceClaim did not create: " + str(scdoc))
        return scdoc

    @staticmethod
    def _rewrite_spaceclaim_package(source: Path, destination: Path,
                                    assembly: Path, scdoc: Path) -> None:
        """Copy a SpaceClaim package and localize only its two hardcoded paths."""
        source_step = r"C:\OpTurbo\Temp Files\open_turbine_assembly.step"
        source_scdoc = r"C:\OpTurbo\Temp Files\open_turbine_assembly.scdoc"
        with ZipFile(source, "r") as archive:
            entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
        updated = []
        found_script = False
        for info, data in entries:
            if info.filename == "_script":
                found_script = True
                script = data.decode("utf-8")
                if source_step not in script or source_scdoc not in script:
                    raise ValueError("The packaged open-turbine SpaceClaim script no longer matches its expected paths.")
                script = script.replace(source_step, windows_path(assembly))
                script = script.replace(source_scdoc, windows_path(scdoc))
                data = script.encode("utf-8")
            updated.append((info, data))
        if not found_script:
            raise ValueError("The open-turbine SpaceClaim package has no _script entry.")
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
            for info, data in updated:
                archive.writestr(info, data)

    def _mesh(self, config: ProjectConfig, scdoc: Path, output: Path) -> Path:
        """Run Workbench/Meshing entirely inside this candidate's mesh folder."""
        geometry = self._geometry_parameters(config)
        self._validate_mesh_settings(config)
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        template = self.workflow_resources / "mesh_script.py"
        mesh_script = output / "open_turbine_mesh_script.py"
        mesh_script.write_text(self._mesh_script(config, geometry, template), encoding="utf-8")
        staged_scdoc = output / "open_turbine_assembly.scdoc"
        if Path(scdoc).resolve() != staged_scdoc.resolve():
            shutil.copy2(scdoc, staged_scdoc)
        project = output / "open_turbine_mesh.wbpj"
        journal = output / "run_open_turbine_meshing.wbjn"
        journal.write_text(
            AnsysMeshingStage.workbench_journal(staged_scdoc, mesh_script, project),
            encoding="utf-8",
        )
        self.emit("[3/4] Generating the open-turbine ANSYS mesh")
        workbench = require_executable(config.tools.workbench, "ANSYS Workbench")
        command = [workbench, "-B", "-R", windows_path(journal)]
        log_path = output / "meshing.log"
        try:
            run_streaming(command, output, log_path, self.emit, self.cancel)
        except RuntimeError:
            # The project belongs to this new candidate and is safe to retry.
            self.emit("Workbench failed; clearing this candidate's scratch project and retrying.")
            project.unlink(missing_ok=True)
            project_files = output / f"{project.stem}_files"
            if project_files.exists():
                shutil.rmtree(project_files)
            time.sleep(3)
            run_streaming(command, output, log_path, self.emit, self.cancel)
        extractor = self.resources / "meshing" / "extract_mesh_artifact.py"
        mesh = output / "open_turbine_assembly.msh"
        run_streaming([sys.executable, str(extractor), "--project", str(project), "--output", str(mesh)],
                      output, log_path, self.emit, self.cancel)
        if not mesh.is_file():
            raise FileNotFoundError("ANSYS Meshing did not export the open-turbine mesh.")
        return mesh

    def _cfd(self, config: ProjectConfig, mesh: Path, output: Path) -> dict:
        """Run the shared Fluent/BEM coupling using the open-turbine case file."""
        case = self.workflow_resources / "fluent" / "open_turbine_assembly.cas.h5"
        if not case.is_file():
            raise FileNotFoundError("Open-turbine Fluent baseline case was not found: " + str(case))
        cfd_settings = replace(config.cfd, source_initialization="conservative",
                               previous_source_weight=1.0)
        run_config = replace(config, cfd=cfd_settings)
        return self.cfd_stage.run(
            run_config, mesh, output, baseline_case=case, case_name=case.name,
        )

    def prepare_mesh_study_geometry(self, config: ProjectConfig,
                                    output: Path) -> tuple[ProjectConfig, Path]:
        """Generate one open-turbine geometry/SCDOC shared by mesh-study candidates."""
        output = Path(output)
        existing_scdoc = output / "02_spaceclaim" / "open_turbine_assembly.scdoc"
        if existing_scdoc.is_file():
            return config, existing_scdoc
        step = self.generate_assembly(config, output)
        scdoc = self._spaceclaim(config, step, output / "02_spaceclaim")
        return config, scdoc

    def evaluate_mesh_study_candidate(self, config: ProjectConfig, scdoc: Path,
                                      candidate_dir: Path) -> dict:
        """Evaluate one mesh-study candidate with the shared open-turbine BEM path."""
        candidate_dir = Path(candidate_dir)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        mesh_dir, cfd_dir = candidate_dir / "03_mesh", candidate_dir / "04_cfd"
        started = time.perf_counter()
        mesh = self._mesh(config, scdoc, mesh_dir)
        mesh_seconds = time.perf_counter() - started
        cell_count = mesh_cell_count(mesh, (mesh_dir / "meshing.log",))
        cfd_started = time.perf_counter()
        result = self._cfd(config, mesh, cfd_dir)
        cfd_seconds = time.perf_counter() - cfd_started
        result.update({
            "status": "completed",
            "workflow_id": "axisymmetric_2d_open_turbine",
            "candidate_dir": str(candidate_dir),
            "mesh": str(mesh),
            "cell_count": mesh_cell_count(mesh, (cfd_dir / "fluent_driver.log",
                                                   mesh_dir / "meshing.log")) or cell_count,
            "meshing_seconds": mesh_seconds,
            "fluent_solution_seconds": cfd_seconds,
            "candidate_seconds": time.perf_counter() - started,
            "outer_iterations": result.get("iteration"),
        })
        atomic_json(candidate_dir / "result.json", result)
        return result

    @staticmethod
    def _mesh_script(config: ProjectConfig, geometry: OpenTurbineParameters,
                     template: Path) -> str:
        """Apply the project's active, duct-free controls to its mesh template."""
        script = Path(template).read_text(encoding="utf-8")
        values = {
            "DOMAIN_HEIGHT_CM = 675.0": f"DOMAIN_HEIGHT_CM = {geometry.domain_height / 10}",
            "HUB_RADIUS_CM = 4.5": f"HUB_RADIUS_CM = {geometry.hub_radius / 10}",
            "DOMAIN_ORIGIN_X_CM = -225.0": f"DOMAIN_ORIGIN_X_CM = {geometry.domain_origin_x / 10}",
            "DOMAIN_LENGTH_CM = 900.0": f"DOMAIN_LENGTH_CM = {geometry.domain_length / 10}",
            "RESOLUTION_LENGTH_CM = 270.0": f"RESOLUTION_LENGTH_CM = {geometry.resolution_length / 10}",
            "RESOLUTION_INLET_RADIUS_CM = 90.0": f"RESOLUTION_INLET_RADIUS_CM = {geometry.resolution_inlet_radius / 10}",
            "GLOBAL_SIZE_CM = 3.0": f"GLOBAL_SIZE_CM = {config.mesh.global_size_cm}",
            "GROWTH_RATE = 1.1": f"GROWTH_RATE = {config.mesh.growth_rate}",
            "CPU_CORES_FOR_PARALLEL_PART_MESHING = None": (
                f"CPU_CORES_FOR_PARALLEL_PART_MESHING = {config.mesh.cpu_cores!r}"
            ),
            'MESH_METHOD = "Quad"': f"MESH_METHOD = {config.mesh.method!r}",
            "CURVATURE_ANGLE_DEG = 5.0": f"CURVATURE_ANGLE_DEG = {config.mesh.curvature_angle_deg}",
            "RESOLUTION_SIZE_CM = 1.0": f"RESOLUTION_SIZE_CM = {config.mesh.resolution_size_cm}",
            "HUB_SIZE_CM = 0.3": f"HUB_SIZE_CM = {config.mesh.hub_size_cm}",
            "INFLATION_ENABLED = True": f"INFLATION_ENABLED = {config.mesh.inflation_enabled!r}",
            "INFLATION_LAYERS = 5": f"INFLATION_LAYERS = {config.mesh.inflation_layers}",
            "INFLATION_MAX_THICKNESS_CM = 0.2": (
                f"INFLATION_MAX_THICKNESS_CM = {config.mesh.inflation_max_thickness_cm}"
            ),
        }
        for old, new in values.items():
            if old not in script:
                raise ValueError(f"Open-turbine mesh template is missing setting marker: {old}")
            script = script.replace(old, new)
        return script

    @staticmethod
    def _validate_mesh_settings(config: ProjectConfig) -> None:
        """Reject invalid active sizing and method values before launching ANSYS."""
        values = (
            config.mesh.global_size_cm, config.mesh.growth_rate,
            config.mesh.curvature_angle_deg, config.mesh.resolution_size_cm,
            config.mesh.hub_size_cm, config.mesh.inflation_layers,
            config.mesh.inflation_max_thickness_cm,
        )
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
               for value in values):
            raise ValueError("Active open-turbine meshing values must be positive finite numbers.")
        if config.mesh.method not in {"Default", "Quad", "Tri", "MultiZone"}:
            raise ValueError("Unsupported ANSYS meshing method: " + config.mesh.method)

    @staticmethod
    def _validate_settings(config: ProjectConfig) -> None:
        """Check inputs and packaged resources before launching external tools."""
        OpenTurbineRunner._geometry_parameters(config)
        OpenTurbineRunner._validate_mesh_settings(config)
        require_executable(config.tools.freecad, "FreeCAD")
        require_executable(config.tools.spaceclaim, "SpaceClaim")
        require_executable(config.tools.workbench, "ANSYS Workbench")
        require_executable(config.tools.fluent, "Fluent")

    def _validate_resources(self) -> None:
        """Reject an incomplete workflow installation before starting FreeCAD."""
        required = (
            self.workflow_resources / "spaceclaim" / "open_turbine_assembly.scscript",
            self.workflow_resources / "mesh_script.py",
            self.workflow_resources / "fluent" / "open_turbine_assembly.cas.h5",
            self.resources / "meshing" / "extract_mesh_artifact.py",
            self.resources / "fluent" / "ad_sources.c",
            self.resources / "fluent" / "libudf",
            self.resources / "cfd_tables",
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("Open-turbine workflow resources are missing: "
                                    + ", ".join(missing))

    @staticmethod
    def _candidate_metadata(config: ProjectConfig,
                            geometry: OpenTurbineParameters) -> dict:
        """Describe the open run without duct or genetic-optimization settings."""
        configuration = config.to_dict()
        configuration.pop("ga", None)
        configuration.pop("design_variables", None)
        configuration["geometry"] = asdict(geometry)
        configuration["mesh"] = {
            key: value for key, value in configuration["mesh"].items()
            if key != "duct_size_cm"
        }
        configuration["tools"].pop("handoff_dir", None)
        configuration["cfd"]["source_initialization"] = "conservative"
        configuration["cfd"]["previous_source_weight"] = 1.0
        cfd_settings = dict(asdict(config.cfd))
        cfd_settings["source_initialization"] = "conservative"
        cfd_settings["previous_source_weight"] = 1.0
        return {
            "workflow_id": "axisymmetric_2d_open_turbine",
            "configuration": configuration,
            "geometry": asdict(geometry),
            "mesh": {key: value for key, value in asdict(config.mesh).items()
                     if key != "duct_size_cm"},
            "cfd": cfd_settings,
        }

    @staticmethod
    def _require_empty_candidate(candidate_dir: Path) -> None:
        """Prevent a candidate run from overwriting existing user results."""
        if candidate_dir.exists() and any(candidate_dir.iterdir()):
            raise FileExistsError(f"Refusing to overwrite candidate results: {candidate_dir}")
