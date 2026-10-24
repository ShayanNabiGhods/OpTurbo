"""Sequential candidate pipeline: STEP, SCDOC, mesh, then CFD/BEM."""

from __future__ import annotations

from dataclasses import asdict, replace
import math
from pathlib import Path
from typing import Callable

from ....models import GeometrySettings, ProjectConfig, VariableSpec
from ..geometry.parameters import nested_parameters, validate_lower_profile, validate_profile
from ....objectives import objective_value
from ....domain.validation import validate_project_settings
from opturbo.pipeline.process import require_executable
from .adapters.fluent import FluentBEMStage
from .candidate import PreparedCandidate
from .mesh_study import MeshStudyPipelineMixin
from .adapters.geometry import FreeCADGeometryStage
from .adapters.meshing import AnsysMeshingStage
from .adapters.spaceclaim import SpaceClaimStage
from ....storage import atomic_json


class PipelineRunner(MeshStudyPipelineMixin):
    """Run one design through the four isolated engineering adapters."""

    def __init__(self, application_root: Path, emit: Callable[[str], None] = print,
                 cancel: Callable[[], bool] | None = None,
                 resources: Path | None = None):
        self.root = Path(application_root)
        self.resources = Path(resources) if resources is not None else self.root / "resources"
        self.emit = emit
        self.cancel = cancel
        self.previous_candidate_sources: Path | None = None
        self.geometry_stage = FreeCADGeometryStage(self)
        self.spaceclaim_stage = SpaceClaimStage(self)
        self.meshing_stage = AnsysMeshingStage(self)
        self.cfd_stage = FluentBEMStage(self)

    def evaluate(self, config: ProjectConfig, genome: dict[str, float], candidate_dir: Path) -> dict:
        """Evaluate one genome and return Cp, Ct, and saved artifact paths."""
        return self.finish(self.prepare(config, genome, candidate_dir))

    def prepare(self, config: ProjectConfig, genome: dict[str, float], candidate_dir: Path) -> PreparedCandidate:
        """Run stages 1–3 serially and copy the mesh out of the shared handoff."""
        validate_project_settings(config)
        self._validate_tool_paths(config)
        variables = [replace(item, value=genome.get(item.key, item.value) if item.optimize else item.value)
                     for item in config.design_variables]
        geometry_overrides = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(config.geometry, **geometry_overrides)
        config = replace(config, geometry=geometry, design_variables=variables)
        validate_project_settings(config)
        parsec = nested_parameters(variables)
        if geometry.design_type == "flanged":
            validate_lower_profile(parsec)
        else:
            validate_profile(parsec)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        geometry_dir = candidate_dir / "01_geometry"
        cad_dir = candidate_dir / "02_spaceclaim"
        mesh_dir = candidate_dir / "03_mesh"
        cfd_dir = candidate_dir / "04_cfd"
        for folder in (geometry_dir, cad_dir, mesh_dir, cfd_dir):
            folder.mkdir(exist_ok=True)
        atomic_json(candidate_dir / "candidate.json", {
            "design_type": geometry.design_type, "parsec": parsec, "geometry": asdict(geometry),
            "mesh": asdict(config.mesh), "cfd": asdict(config.cfd),
            "genome": genome, "configuration": config.to_dict(),
        })
        assembly = self._geometry(config, geometry, parsec, geometry_dir)
        scdoc = self._spaceclaim(config, assembly, cad_dir)
        mesh = self._mesh(config, scdoc, mesh_dir)
        atomic_json(candidate_dir / "preparation.json", {"status": "prepared", "mesh": str(mesh)})
        return PreparedCandidate(config, candidate_dir, mesh)

    def finish(self, prepared: PreparedCandidate) -> dict:
        """Run stage 4 using only the candidate's own mesh and working folder."""
        result = self._cfd(prepared.config, prepared.mesh, prepared.folder / "04_cfd")
        return self._finalize_result(prepared, result)

    def _finalize_result(self, prepared: PreparedCandidate, result: dict) -> dict:
        """Add normalized performance values and persist a completed CFD result."""
        if not math.isfinite(float(result["cp"])) or not math.isfinite(float(result["ct"])):
            raise ValueError("CFD returned a non-finite Cp or Ct.")
        geometry = prepared.config.geometry
        lower_te = next((item.value for item in prepared.config.design_variables
                         if item.key == "lower.trailing_edge_height"), 0.0)
        flange_length = geometry.duct_flange_length if geometry.design_type == "flanged" else 0.0
        duct_y_max_mm = (
            geometry.duct_origin_r
            + flange_length * math.sin(math.radians(geometry.duct_flange_angle_deg))
            + geometry.duct_chord * math.sin(math.radians(geometry.duct_angle_deg))
            + lower_te * geometry.duct_chord
        )
        duct_tip_radius_m = duct_y_max_mm / 1000.0
        rotor_radius = prepared.config.cfd.rotor_radius_m
        if not math.isfinite(duct_tip_radius_m) or duct_tip_radius_m <= 0:
            raise ValueError("Calculated duct-tip radius must be positive and finite.")
        area_ratio = (rotor_radius / duct_tip_radius_m) ** 2
        result["cp_normalized"] = float(result["cp"]) * area_ratio
        result["ct_normalized"] = float(result["ct"]) * area_ratio
        result["duct_tip_radius_m"] = duct_tip_radius_m
        result["objective"] = prepared.config.ga.objective
        result["fitness"] = objective_value(result, prepared.config.ga.objective)
        result["candidate_dir"] = str(prepared.folder)
        atomic_json(prepared.folder / "result.json", result)
        final_sources = prepared.folder / "04_cfd" / "fluent" / "final_ad_sources.dat"
        if final_sources.is_file():
            self.previous_candidate_sources = final_sources
        return result



    @staticmethod
    def _validate_tool_paths(config: ProjectConfig) -> None:
        """Confirm every required executable exists before a workflow starts."""
        tools = (
            ("FreeCAD", config.tools.freecad),
            ("SpaceClaim", config.tools.spaceclaim),
            ("ANSYS Workbench", config.tools.workbench),
            ("Fluent", config.tools.fluent),
        )
        for name, path in tools:
            require_executable(path, name)

    def _geometry(self, config: ProjectConfig, geometry: GeometrySettings,
                  parsec: dict, output: Path) -> Path:
        """Compatibility wrapper for the FreeCAD stage."""
        return self.geometry_stage.run(config, geometry, parsec, output)

    def _spaceclaim(self, config: ProjectConfig, assembly: Path, output: Path) -> Path:
        """Compatibility wrapper for the SpaceClaim stage."""
        return self.spaceclaim_stage.run(config, assembly, output)

    def _mesh(self, config: ProjectConfig, scdoc: Path, output: Path) -> Path:
        """Compatibility wrapper for the ANSYS meshing stage."""
        return self.meshing_stage.run(config, scdoc, output)

    @staticmethod
    def _workbench_journal(scdoc: Path, mesh_script: Path, project: Path) -> str:
        """Build a Workbench journal with candidate-specific paths."""
        return AnsysMeshingStage.workbench_journal(scdoc, mesh_script, project)

    def _cfd(self, config: ProjectConfig, mesh: Path, output: Path) -> dict:
        """Compatibility wrapper for the Fluent/BEM stage."""
        return self.cfd_stage.run(
            config, mesh, output, self.previous_candidate_sources
        )
