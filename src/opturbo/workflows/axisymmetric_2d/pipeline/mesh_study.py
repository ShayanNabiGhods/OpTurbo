"""Mesh-study pipeline operations shared by the current GUI and runner."""

from dataclasses import asdict, replace
from pathlib import Path
import time

from ..mesh_study import mesh_cell_count
from ....models import ProjectConfig
from ..geometry.parameters import nested_parameters, validate_lower_profile, validate_profile
from ....storage import atomic_json
from ....domain.validation import validate_project_settings
from .candidate import PreparedCandidate


class MeshStudyPipelineMixin:
    """Prepare shared study geometry and evaluate each mesh configuration."""

    def prepare_mesh_study_geometry(self, config: ProjectConfig, output: Path) -> tuple[ProjectConfig, Path]:
        """Generate one selected design and SpaceClaim document for a mesh study."""
        validate_project_settings(config)
        self._validate_tool_paths(config)
        variables = [replace(item) for item in config.design_variables]
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(config.geometry, **geometry_values)
        config = replace(config, geometry=geometry, design_variables=variables)
        parsec = nested_parameters(variables)
        if geometry.design_type == "flanged":
            validate_lower_profile(parsec)
        else:
            validate_profile(parsec)
        output = Path(output)
        geometry_dir, cad_dir = output / "01_geometry", output / "02_spaceclaim"
        geometry_dir.mkdir(parents=True, exist_ok=True)
        cad_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(output / "study_geometry.json", {
            "design_type": geometry.design_type,
            "parsec": parsec,
            "geometry": asdict(geometry),
            "configuration": config.to_dict(),
        })
        self.emit("[1/2] Generating shared FreeCAD geometry for the mesh study")
        assembly = self._geometry(config, geometry, parsec, geometry_dir)
        self.emit("[2/2] Preparing shared SpaceClaim document for the mesh study")
        scdoc = self._spaceclaim(config, assembly, cad_dir)
        return config, scdoc

    def evaluate_mesh_study_candidate(self, config: ProjectConfig, scdoc: Path,
                                      candidate_dir: Path) -> dict:
        """Mesh and solve one study setup against the shared geometry."""
        validate_project_settings(config)
        self._validate_tool_paths(config)
        candidate_dir = Path(candidate_dir)
        mesh_dir, cfd_dir = candidate_dir / "03_mesh", candidate_dir / "04_cfd"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        cfd_dir.mkdir(parents=True, exist_ok=True)
        mesh_started = time.perf_counter()
        try:
            mesh = self._mesh(config, Path(scdoc), mesh_dir)
        except Exception as error:
            try:
                error.mesh_study_metrics = {"meshing_seconds": time.perf_counter() - mesh_started}
            except Exception:
                pass
            raise
        mesh_seconds = time.perf_counter() - mesh_started
        cell_count = mesh_cell_count(mesh, (mesh_dir / "meshing.log",))
        prepared = PreparedCandidate(config, candidate_dir, mesh)
        cfd_started = time.perf_counter()
        try:
            raw_result = self._cfd(config, mesh, cfd_dir)
        except Exception as error:
            try:
                error.mesh_study_metrics = {
                    "cell_count": mesh_cell_count(
                        mesh, (cfd_dir / "fluent_driver.log", mesh_dir / "meshing.log")) or cell_count,
                    "meshing_seconds": mesh_seconds,
                    "fluent_solution_seconds": time.perf_counter() - cfd_started,
                    "candidate_seconds": time.perf_counter() - mesh_started,
                }
            except Exception:
                pass
            raise
        fluent_seconds = time.perf_counter() - cfd_started
        result = self._finalize_result(prepared, raw_result)
        result.update({
            "mesh_settings": asdict(config.mesh),
            "cell_count": mesh_cell_count(
                mesh, (cfd_dir / "fluent_driver.log", mesh_dir / "meshing.log")) or cell_count,
            "meshing_seconds": mesh_seconds,
            "fluent_solution_seconds": fluent_seconds,
            "candidate_seconds": mesh_seconds + fluent_seconds,
            "outer_iterations": raw_result.get("iteration"),
        })
        atomic_json(candidate_dir / "mesh_study_result.json", result)
        return result
