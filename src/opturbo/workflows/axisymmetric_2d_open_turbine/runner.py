"""FreeCAD-only candidate pipeline for open-turbine STEP handoff."""

from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import sys
import time
from typing import Callable

from ...models import ProjectConfig
from ...pipeline.process import require_executable, run_streaming, windows_path
from ...storage import atomic_json
from ..axisymmetric_2d.pipeline.adapters.meshing import AnsysMeshingStage
from ...paths import APPLICATION_ROOT
from .geometry.parameters import OUTPUT_NAMES, OpenTurbineParameters
from .geometry.validation import validate_parameters


class OpenTurbineRunner:
    """Generate open-turbine geometry and mesh handoffs without Fluent."""

    preparation_only = True

    def __init__(self, application_root: Path, emit: Callable[[str], None] = print,
                 cancel: Callable[[], bool] | None = None):
        self.root = Path(application_root)
        self.emit = emit
        self.cancel = cancel

    def generate_assembly(self, config: ProjectConfig, candidate_dir: Path) -> Path:
        """Build candidate-owned STEP files and copy them to a unique handoff."""
        geometry = OpenTurbineParameters(**{
            name: getattr(config.geometry, name)
            for name in OpenTurbineParameters.__dataclass_fields__
        })
        validate_parameters(geometry)
        freecad = require_executable(config.tools.freecad, "FreeCAD")
        candidate_dir = Path(candidate_dir)
        if candidate_dir.exists() and any(candidate_dir.iterdir()):
            raise FileExistsError(f"Refusing to overwrite candidate results: {candidate_dir}")
        geometry_dir = candidate_dir / "01_geometry"
        geometry_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(candidate_dir / "candidate.json", {
            "workflow_id": "axisymmetric_2d_open_turbine",
            "configuration": config.to_dict(),
            "geometry": asdict(geometry),
        })
        settings_path = geometry_dir / "open_turbine_settings.json"
        atomic_json(settings_path, asdict(geometry))
        worker = self.root / "src" / "opturbo" / "workflows" \
            / "axisymmetric_2d_open_turbine" / "geometry_worker.py"
        command = [sys.executable, str(worker), "--config", str(settings_path),
                   "--out", str(geometry_dir), "--freecad", freecad]
        self.emit("[1/1] Generating open-turbine STEP assembly with FreeCAD")
        run_streaming(command, self.root, geometry_dir / "freecad.log", self.emit, self.cancel)
        candidate_assembly = geometry_dir / OUTPUT_NAMES["assembly"]
        missing = [name for name in OUTPUT_NAMES.values()
                   if not (geometry_dir / name).is_file()]
        if missing:
            raise FileNotFoundError("FreeCAD did not create required STEP files: " + ", ".join(missing))

        handoff_dir = self._reserve_handoff_folder(Path(config.tools.handoff_dir))
        try:
            for name in OUTPUT_NAMES.values():
                shutil.copy2(geometry_dir / name, handoff_dir / name)
        except OSError:
            shutil.rmtree(handoff_dir, ignore_errors=True)
            raise
        handoff_assembly = handoff_dir / OUTPUT_NAMES["assembly"]
        atomic_json(candidate_dir / "result.json", {
            "status": "step_assembly_created",
            "assembly": str(handoff_assembly),
            "candidate_assembly": str(candidate_assembly),
            "handoff_directory": str(handoff_dir),
            "parts": [str(handoff_dir / name) for name in OUTPUT_NAMES.values()],
        })
        self.emit(f"Open-turbine STEP assembly created: {handoff_assembly}")
        return handoff_assembly

    def generate_mesh(self, config: ProjectConfig, candidate_dir: Path) -> Path:
        """Mesh the manually generated SCDOC and save an open-turbine mesh handoff."""
        geometry = OpenTurbineParameters(**{
            name: getattr(config.geometry, name)
            for name in OpenTurbineParameters.__dataclass_fields__
        })
        validate_parameters(geometry)
        self._validate_mesh_settings(config)
        workbench = require_executable(config.tools.workbench, "ANSYS Workbench")
        handoff_root = Path(config.tools.handoff_dir)
        scdoc = handoff_root / "open_turbine_assembly.scdoc"
        if not scdoc.is_file():
            raise FileNotFoundError(
                "Run the open-turbine SpaceClaim script first. Expected: " + str(scdoc)
            )

        candidate_dir = Path(candidate_dir)
        if candidate_dir.exists() and any(candidate_dir.iterdir()):
            raise FileExistsError(f"Refusing to overwrite candidate results: {candidate_dir}")
        geometry_dir = candidate_dir / "01_geometry"
        spaceclaim_dir = candidate_dir / "02_spaceclaim"
        mesh_dir = candidate_dir / "03_mesh"
        for folder in (geometry_dir, spaceclaim_dir, mesh_dir):
            folder.mkdir(parents=True, exist_ok=True)
        assembly = handoff_root / OUTPUT_NAMES["assembly"]
        if assembly.is_file():
            shutil.copy2(assembly, geometry_dir / OUTPUT_NAMES["assembly"])
        shutil.copy2(scdoc, spaceclaim_dir / scdoc.name)
        atomic_json(candidate_dir / "candidate.json", {
            "workflow_id": "axisymmetric_2d_open_turbine",
            "configuration": config.to_dict(),
            "geometry": asdict(geometry),
            "mesh": {key: value for key, value in asdict(config.mesh).items()
                     if key != "duct_size_cm"},
            "spaceclaim_scdoc": str(scdoc),
        })

        script_path = mesh_dir / "open_turbine_mesh_script.py"
        script_path.write_text(self._mesh_script(config, geometry), encoding="utf-8")
        stage_dir = self._reserve_mesh_handoff_folder(handoff_root)
        staged_scdoc = stage_dir / scdoc.name
        staged_script = stage_dir / script_path.name
        shutil.copy2(scdoc, staged_scdoc)
        shutil.copy2(script_path, staged_script)
        project = stage_dir / "open_turbine_mesh.wbpj"
        journal = stage_dir / "run_open_turbine_meshing.wbjn"
        journal.write_text(
            AnsysMeshingStage.workbench_journal(staged_scdoc, staged_script, project),
            encoding="utf-8",
        )
        candidate_journal = mesh_dir / journal.name
        shutil.copy2(journal, candidate_journal)

        self.emit("[3/4] Generating the open-turbine ANSYS mesh")
        command = [workbench, "-B", "-R", windows_path(journal)]
        log_path = mesh_dir / "meshing.log"
        try:
            run_streaming(command, stage_dir, log_path, self.emit, self.cancel)
        except RuntimeError:
            self.emit("Workbench failed once; clearing this new scratch project and retrying.")
            project.unlink(missing_ok=True)
            project_files = stage_dir / f"{project.stem}_files"
            if project_files.exists():
                shutil.rmtree(project_files)
            time.sleep(3)
            run_streaming(command, stage_dir, log_path, self.emit, self.cancel)

        extractor = APPLICATION_ROOT / "resources" / "meshing" / "extract_mesh_artifact.py"
        candidate_mesh = mesh_dir / "open_turbine_assembly.msh"
        run_streaming(
            [sys.executable, str(extractor), "--project", str(project), "--output", str(candidate_mesh)],
            mesh_dir, log_path, self.emit, self.cancel,
        )
        if not candidate_mesh.is_file():
            raise FileNotFoundError("ANSYS Meshing did not export the open-turbine mesh.")
        handoff_mesh = stage_dir / candidate_mesh.name
        shutil.copy2(candidate_mesh, handoff_mesh)
        atomic_json(candidate_dir / "result.json", {
            "status": "mesh_created",
            "workflow_id": "axisymmetric_2d_open_turbine",
            "mesh": str(handoff_mesh),
            "candidate_mesh": str(candidate_mesh),
            "scdoc": str(scdoc),
            "workbench_project": str(project),
        })
        self.emit(f"Open-turbine mesh created: {handoff_mesh}")
        return handoff_mesh

    @staticmethod
    def _validate_mesh_settings(config: ProjectConfig) -> None:
        """Validate the mesh controls used by the duct-free meshing script."""
        values = (
            config.mesh.global_size_cm, config.mesh.growth_rate,
            config.mesh.curvature_angle_deg, config.mesh.resolution_size_cm,
            config.mesh.hub_size_cm, config.mesh.inflation_layers,
            config.mesh.inflation_max_thickness_cm,
        )
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
               for value in values):
            raise ValueError("Active open-turbine meshing values must be positive numbers.")
        if config.mesh.method not in {"Default", "Quad", "Tri", "MultiZone"}:
            raise ValueError("Unsupported ANSYS meshing method: " + config.mesh.method)

    @staticmethod
    def _mesh_script(config: ProjectConfig, geometry: OpenTurbineParameters) -> str:
        """Return the open-turbine meshing script with project settings applied."""
        template = (APPLICATION_ROOT / "resources" / "workflows"
                    / "axisymmetric_2d_open_turbine" / "mesh_script.py")
        script = template.read_text(encoding="utf-8")
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
            "INFLATION_MAX_THICKNESS_CM = 0.2": f"INFLATION_MAX_THICKNESS_CM = {config.mesh.inflation_max_thickness_cm}",
        }
        for old, new in values.items():
            if old not in script:
                raise ValueError(f"Open-turbine mesh template is missing its setting marker: {old}")
            script = script.replace(old, new)
        return script

    @staticmethod
    def _reserve_mesh_handoff_folder(root: Path) -> Path:
        """Create a unique Workbench and Fluent-mesh handoff directory."""
        root.mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            folder = root / f"open_turbine_mesh_run_{index:03d}"
            try:
                folder.mkdir()
                return folder
            except FileExistsError:
                index += 1

    @staticmethod
    def _reserve_handoff_folder(root: Path) -> Path:
        """Create the next numbered handoff folder without replacing prior files."""
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        index = 1
        while True:
            folder = root / f"open_turbine_run_{index:03d}"
            try:
                folder.mkdir()
                return folder
            except FileExistsError:
                index += 1
