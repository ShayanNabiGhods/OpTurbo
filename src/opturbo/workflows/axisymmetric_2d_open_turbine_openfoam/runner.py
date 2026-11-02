"""FreeCAD, body-fitted blockMesh, and OpenFOAM/BEM candidate pipeline."""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
from typing import Callable
import uuid

from ...models import ProjectConfig
from ...pipeline.process import require_executable, run_streaming
from ...storage import atomic_json
from ..axisymmetric_2d_open_turbine.geometry.parameters import OUTPUT_NAMES, OpenTurbineParameters
from ..axisymmetric_2d_open_turbine.runner import OpenTurbineRunner
from ..axisymmetric_2d.cfd.bem import performance, solve, sources_from
from ..axisymmetric_2d.cfd.coupling import initial_sources, relax, write_source_terms
from ..axisymmetric_2d.cfd.resources import load_airfoil, load_blade, load_setup
from .case import (
    axis_core_radius_m,
    radial_zone_edges,
    write_block_mesh_dict,
    write_case_fields,
    write_fv_models,
    write_system_dictionaries,
    write_topo_set_dict,
)


SURFACE_NAME = "openfoam_hub.stl"
SURFACE_PROFILE_NAME = "openfoam_hub_profile.json"
WORKFLOW_ID = "axisymmetric_2d_open_turbine_openfoam"
_FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_VECTOR = re.compile(rf"\(\s*({_FLOAT})\s+({_FLOAT})\s+({_FLOAT})\s*\)")


def windows_path_to_wsl(path: Path | str, mount_root: str = "/mnt") -> str:
    """Translate a Windows drive path to the standard WSL mount layout."""
    raw = str(Path(path).resolve()) if isinstance(path, Path) else str(path)
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", raw)
    if match:
        drive, remainder = match.groups()
        pieces = [piece for piece in re.split(r"[\\/]+", remainder) if piece]
        return "/".join((mount_root.rstrip("/"), drive.lower(), *pieces))
    if raw.startswith("/"):
        return raw
    raise ValueError(f"Cannot map this path into WSL: {raw}")


class OpenFoamOpenTurbineRunner(OpenTurbineRunner):
    """Run an axisymmetric open turbine through FreeCAD and OpenFOAM 14."""

    run_only = True

    def __init__(self, application_root: Path, emit: Callable[[str], None] = print,
                 cancel: Callable[[], bool] | None = None):
        super().__init__(application_root, emit=emit, cancel=cancel)
        self.resources = self.root / "resources" / "workflows" / WORKFLOW_ID
        self.workflow_resources = self.resources
        self.current_stage = "setup"
        self._wsl_case_paths: dict[str, str] = {}
        self._active_wsl_case: str | None = None

    def generate_assembly(self, config: ProjectConfig, candidate_dir: Path) -> Path:
        """Export the shared STEP assembly plus the SI-unit hub STL in FreeCAD."""
        geometry = self._geometry_parameters(config)
        candidate_dir = Path(candidate_dir)
        self._require_empty_candidate(candidate_dir)
        geometry_dir = candidate_dir / "01_geometry"
        geometry_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(geometry_dir / "open_turbine_settings.json", asdict(geometry))
        worker = (self.root / "src" / "opturbo" / "workflows"
                  / "axisymmetric_2d_open_turbine" / "geometry_worker.py")
        command = [
            sys.executable, str(worker), "--config",
            str(geometry_dir / "open_turbine_settings.json"), "--out", str(geometry_dir),
            "--freecad", require_executable(config.tools.freecad, "FreeCAD"),
            "--openfoam-surface",
        ]
        self.emit("[1/3] Generating open-turbine geometry and hub STL with FreeCAD")
        run_streaming(command, self.root, geometry_dir / "freecad.log", self.emit, self.cancel)
        missing = [name for name in OUTPUT_NAMES.values() if not (geometry_dir / name).is_file()]
        missing.extend(name for name in (SURFACE_NAME, SURFACE_PROFILE_NAME)
                       if not (geometry_dir / name).is_file())
        if missing:
            raise FileNotFoundError("FreeCAD did not create required OpenFOAM geometry files: "
                                    + ", ".join(missing))
        atomic_json(candidate_dir / "candidate.json", self._candidate_metadata(config, geometry))
        return geometry_dir / OUTPUT_NAMES["assembly"]

    def evaluate(self, config: ProjectConfig, candidate_dir: Path) -> dict:
        """Run the FreeCAD-to-OpenFOAM pipeline and save Cp/Ct plus diagnostics."""
        candidate_dir = Path(candidate_dir)
        self._require_empty_candidate(candidate_dir)
        try:
            self._validate_settings(config)
            self._validate_resources()
            self._bem_inputs(config)
            self.current_stage = "FreeCAD geometry"
            self.generate_assembly(config, candidate_dir)
            self.current_stage = "WSL/OpenFOAM preflight"
            self._preflight(config, candidate_dir / "02_mesh" / "wsl_preflight.log")
            geometry_dir = candidate_dir / "01_geometry"
            self.current_stage = "OpenFOAM meshing"
            case_dir = self._mesh(config, geometry_dir / SURFACE_NAME,
                                  candidate_dir / "02_mesh")
            atomic_json(candidate_dir / "preparation.json", {
                "status": "prepared", "case": str(case_dir),
                "mesh": str(case_dir / "constant" / "polyMesh"),
            })
            self.current_stage = "OpenFOAM CFD/BEM coupling"
            result = self._cfd(config, case_dir, candidate_dir / "03_cfd")
            cp, ct = float(result["cp"]), float(result["ct"])
            if not math.isfinite(cp) or not math.isfinite(ct):
                raise ValueError("OpenFOAM/BEM returned non-finite Cp or Ct values.")
            result.update({
                "status": "completed",
                "workflow_id": WORKFLOW_ID,
                "candidate_dir": str(candidate_dir),
                "mesh": str(case_dir / "constant" / "polyMesh"),
                "case": str(case_dir),
                "mesh_cells": self._cell_count(case_dir.parent / "meshing.log"),
            })
            atomic_json(candidate_dir / "result.json", result)
            self.emit(f"OpenFOAM/BEM performance evaluation completed: Cp={cp:.7g}, Ct={ct:.7g}")
            return result
        except Exception as error:
            atomic_json(candidate_dir / "failure.json", {
                "status": "failed", "workflow_id": WORKFLOW_ID,
                "candidate_dir": str(candidate_dir), "stage": self.current_stage,
                "error": str(error),
                "wsl_scratch_case": self._active_wsl_case,
            })
            raise

    def _mesh(self, config: ProjectConfig, hub_surface: Path, output: Path) -> Path:
        """Generate the wedge mesh, snap the FreeCAD hub, and define source zones."""
        output = Path(output)
        case_dir = output / "openfoam_case"
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "system").mkdir(parents=True, exist_ok=True)
        tri_surface = case_dir / "constant" / "triSurface"
        tri_surface.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hub_surface, tri_surface / "hub.stl")
        blade, turbine, _flow, _airfoil = self._bem_inputs(config)
        geometry = self._geometry_parameters(config)
        profile_path = hub_surface.with_name(SURFACE_PROFILE_NAME)
        if not profile_path.is_file():
            raise FileNotFoundError("FreeCAD did not export the hub profile for body-fitted blockMesh.")
        profile_points = json.loads(profile_path.read_text(encoding="utf-8"))["points"]
        nx, nr = write_block_mesh_dict(case_dir / "system" / "blockMeshDict",
                                       geometry, config.mesh, config.openfoam, profile_points)
        write_case_fields(case_dir, geometry, config.cfd, config.openfoam,
                          config.cfd.viscous_model)
        write_system_dictionaries(
            case_dir, config.cfd, config.openfoam, config.cfd.viscous_model,
            blade, geometry.actuator_origin_x / 1000,
        )
        edges = radial_zone_edges(blade, turbine)
        write_topo_set_dict(case_dir / "system" / "topoSetDict", edges,
                            geometry, config.cfd)
        wsl_case = self._new_wsl_case(config)
        self._active_wsl_case = wsl_case
        self._wsl_case_paths[str(case_dir.resolve())] = wsl_case
        log = output / "meshing.log"
        self.emit("Staging the case on the WSL Linux filesystem")
        self._copy_case_to_wsl(config, case_dir, wsl_case, log)
        self.emit("[2/3] Creating the FreeCAD-profile-fitted wedge mesh with blockMesh")
        self._run_openfoam(config, wsl_case, "blockMesh", log)
        self._run_openfoam(config, wsl_case,
                           "surfaceCheck constant/triSurface/hub.stl", log)
        self._run_openfoam(config, wsl_case, "checkMesh -allTopology -allGeometry", log)
        self._validate_mesh_quality(log)
        self._run_openfoam(config, wsl_case, "topoSet", log)
        self._sync_case_from_wsl(config, wsl_case, case_dir, log)
        zone_counts = self._zone_counts(case_dir / "constant" / "polyMesh" / "cellZones")
        expected_zones = len(blade.radius)
        if len(zone_counts) != expected_zones or any(count < 1 for count in zone_counts.values()):
            raise RuntimeError(
                "OpenFOAM did not create cells in every BEM actuator band. "
                "Reduce BEM stations or refine the OpenFOAM mesh around the rotor."
            )
        atomic_json(output / "mesh_info.json", {
            "block_mesh_cells": nx * nr,
            "axial_cells": nx,
            "radial_cells": nr,
            "axis_core_radius_m": axis_core_radius_m(geometry, config.mesh),
            "cell_count": self._cell_count(log),
            "actuator_band_cell_counts": zone_counts,
            "case": str(case_dir),
        })
        return case_dir

    def _cfd(self, config: ProjectConfig, case_dir: Path, output: Path) -> dict:
        """Iterate simpleFoam and the shared BEM model through radial sources."""
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        table_source = self.resources / "cfd_tables"
        tables = output / "resources"
        if not table_source.is_dir():
            raise FileNotFoundError("OpenFOAM workflow BEM tables are missing: " + str(table_source))
        shutil.copytree(table_source, tables, dirs_exist_ok=True)
        blade, turbine, flow, airfoil = self._bem_inputs(config, tables)
        wsl_case = self._wsl_case_paths.get(str(Path(case_dir).resolve()))
        if not wsl_case:
            raise RuntimeError("OpenFOAM WSL scratch case was not prepared for this mesh.")
        axial, tangential = initial_sources(blade)
        history = output / "iteration_history"
        history.mkdir(parents=True, exist_ok=True)
        log = output / "openfoam_driver.log"
        previous_cp = previous_ct = 0.0
        latest = None
        start_time = 0.0
        for iteration in range(1, config.cfd.max_outer_iterations + 1):
            self.emit(f"[3/3] OpenFOAM/BEM coupling iteration {iteration}/"
                      f"{config.cfd.max_outer_iterations}")
            write_fv_models(case_dir / "constant" / "fvModels", axial, tangential,
                            config.cfd.density_kg_m3)
            end_time = math.ceil(start_time + config.cfd.fluent_iterations)
            write_system_dictionaries(
                case_dir, config.cfd, config.openfoam, config.cfd.viscous_model,
                blade, config.geometry.actuator_origin_x / 1000, end_time=end_time,
            )
            self._copy_cfd_settings_to_wsl(config, case_dir, wsl_case, log)
            self._run_openfoam(config, wsl_case, "simpleFoam", log)
            start_time = float(end_time)
            self._copy_probes_from_wsl(config, case_dir, wsl_case, log)
            velocities = self._read_probes(case_dir, len(blade.radius))
            axial_velocity = [value[0] for value in velocities]
            tangential_velocity = [value[2] for value in velocities]
            bem = solve(flow, turbine, blade, airfoil, axial_velocity, tangential_velocity)
            value = performance(flow, turbine, blade, bem)
            if not math.isfinite(value.cp) or not math.isfinite(value.ct):
                raise RuntimeError(f"Non-finite OpenFOAM/BEM result at outer iteration {iteration}.")
            latest = {
                "iteration": iteration, "cp": value.cp, "ct": value.ct,
                "thrust": value.thrust, "torque": value.torque, "power": value.power,
                "actuator_thickness_m": blade.thickness,
                "a": bem.a, "a_prime": bem.ap, "phi_deg": bem.phi,
                "alpha_deg": bem.alpha, "reynolds": bem.reynolds,
                "loss_factor": bem.loss, "tip_loss_model": turbine.tip_loss_model,
                "radius_m": blade.radius,
                "axial_velocity_m_s": axial_velocity,
                "tangential_velocity_m_s": tangential_velocity,
                "openfoam_time": start_time,
            }
            atomic_json(history / f"bem_results_iter{iteration:02d}.json", latest)
            atomic_json(output / "latest_result.json", latest)
            write_source_terms(history / f"ad_sources_iter{iteration:02d}.dat",
                               blade, axial, tangential)
            new_sources = sources_from(bem)
            axial = relax(axial, new_sources.axial, config.cfd.relaxation)
            tangential = relax(tangential, new_sources.tangential, config.cfd.relaxation)
            write_source_terms(output / "final_ad_sources.dat", blade, axial, tangential)
            self.emit(f"outer {iteration:02d}: Cp={value.cp:.6f}, Ct={value.ct:.6f}")
            if max(abs(value.cp - previous_cp), abs(value.ct - previous_ct)) < config.cfd.tolerance:
                break
            previous_cp, previous_ct = value.cp, value.ct
        if latest is None:
            raise RuntimeError("OpenFOAM/BEM coupling completed no outer iterations.")
        latest["outer_iterations"] = latest["iteration"]
        latest["solver_iterations_per_outer"] = config.cfd.fluent_iterations
        latest["mesh_cells"] = self._cell_count(case_dir.parent / "meshing.log")
        atomic_json(output / "latest_result.json", latest)
        self._sync_case_from_wsl(config, wsl_case, case_dir, log)
        if not config.cfd.keep_iteration_data:
            self._keep_latest_solution(case_dir)
        self._cleanup_wsl_case(config, wsl_case, log)
        self._wsl_case_paths.pop(str(Path(case_dir).resolve()), None)
        self._active_wsl_case = None
        return latest

    def prepare_mesh_study_geometry(self, config: ProjectConfig,
                                    output: Path) -> tuple[ProjectConfig, Path]:
        """Create one shared FreeCAD hub surface for OpenFOAM mesh candidates."""
        output = Path(output)
        surface = output / "01_geometry" / SURFACE_NAME
        if surface.is_file():
            return config, surface
        self._validate_settings(config)
        self.generate_assembly(config, output)
        self._preflight(config, output / "02_mesh" / "wsl_preflight.log")
        return config, surface

    def evaluate_mesh_study_candidate(self, config: ProjectConfig, hub_surface: Path,
                                      candidate_dir: Path) -> dict:
        """Run a mesh candidate and report cell count, elapsed time, Cp, and Ct."""
        candidate_dir = Path(candidate_dir)
        started = time.perf_counter()
        mesh_started = time.perf_counter()
        try:
            case_dir = self._mesh(config, hub_surface, candidate_dir / "02_mesh")
        except Exception as error:
            error.mesh_study_metrics = {
                "meshing_seconds": time.perf_counter() - mesh_started,
            }
            raise
        mesh_seconds = time.perf_counter() - mesh_started
        cfd_started = time.perf_counter()
        result = self._cfd(config, case_dir, candidate_dir / "03_cfd")
        cfd_seconds = time.perf_counter() - cfd_started
        result.update({
            "status": "completed", "workflow_id": WORKFLOW_ID,
            "candidate_dir": str(candidate_dir), "case": str(case_dir),
            "mesh": str(case_dir / "constant" / "polyMesh"),
            "cell_count": self._cell_count(candidate_dir / "02_mesh" / "meshing.log"),
            "meshing_seconds": mesh_seconds,
            "fluent_solution_seconds": cfd_seconds,
            "openfoam_solution_seconds": cfd_seconds,
            "candidate_seconds": time.perf_counter() - started,
            "outer_iterations": result.get("iteration"),
        })
        atomic_json(candidate_dir / "result.json", result)
        return result

    def _preflight(self, config: ProjectConfig, log: Path) -> None:
        """Confirm that the selected WSL distro has a sourced OpenFOAM install."""
        self._run_openfoam(
            config, None,
            "for tool in blockMesh surfaceCheck checkMesh topoSet simpleFoam; "
            "do command -v \"$tool\"; done; "
            "printf 'OpenFOAM version: %s\\n' \"$WM_PROJECT_VERSION\"",
            log,
        )

    def _run_openfoam(self, config: ProjectConfig, case_dir: Path | str | None,
                      command_text: str, log: Path) -> None:
        """Run one command inside WSL with live project progress and logging."""
        executable = require_executable(config.tools.wsl_executable, "WSL")
        distro = config.tools.wsl_distribution.strip()
        bashrc = config.tools.openfoam_bashrc.strip()
        if not distro:
            raise ValueError("Set the exact WSL distribution name in Project / Installed engineering tools.")
        if not bashrc.startswith("/"):
            raise ValueError("OpenFOAM environment script must be an absolute WSL path, such as /opt/openfoam14/etc/bashrc.")
        setup = f"source {shlex.quote(bashrc)}"
        if case_dir is not None:
            wsl_case = (str(case_dir) if isinstance(case_dir, str) and str(case_dir).startswith("/")
                        else windows_path_to_wsl(case_dir, config.tools.wsl_mount_root))
            setup += f" && cd {shlex.quote(wsl_case)}"
        script = f"set -e; {setup} && {command_text}"
        args = [executable, "--distribution", distro, "--exec", "bash", "-lc", script]
        run_streaming(args, self.root, Path(log), self.emit, self.cancel)

    def _new_wsl_case(self, config: ProjectConfig) -> str:
        """Allocate a unique, space-free case directory on the WSL Linux filesystem."""
        root = config.tools.wsl_work_root.strip().rstrip("/")
        if not root.startswith("/") or re.search(r"\s", root):
            raise ValueError("Set the OpenFOAM WSL scratch folder to an absolute path without spaces, such as /tmp/opturbo-openfoam.")
        return f"{root}/run_{uuid.uuid4().hex}"

    def _copy_case_to_wsl(self, config: ProjectConfig, case_dir: Path,
                          wsl_case: str, log: Path) -> None:
        """Copy generated inputs from the project drive to a WSL-native case path."""
        source = windows_path_to_wsl(case_dir, config.tools.wsl_mount_root)
        parent = str(Path(wsl_case).parent).replace("\\", "/")
        command = (f"mkdir -p {shlex.quote(parent)} && "
                   f"cp -a {shlex.quote(source)} {shlex.quote(wsl_case)}")
        self._run_openfoam(config, None, command, log)

    def _copy_cfd_settings_to_wsl(self, config: ProjectConfig, case_dir: Path,
                                  wsl_case: str, log: Path) -> None:
        """Update source and run controls without copying the large mesh again."""
        source_models = windows_path_to_wsl(case_dir / "constant" / "fvModels",
                                            config.tools.wsl_mount_root)
        source_control = windows_path_to_wsl(case_dir / "system" / "controlDict",
                                             config.tools.wsl_mount_root)
        command = (
            f"cp -f {shlex.quote(source_models)} {shlex.quote(wsl_case + '/constant/fvModels')} && "
            f"cp -f {shlex.quote(source_control)} {shlex.quote(wsl_case + '/system/controlDict')}"
        )
        self._run_openfoam(config, None, command, log)

    def _copy_probes_from_wsl(self, config: ProjectConfig, case_dir: Path,
                              wsl_case: str, log: Path) -> None:
        """Copy only actuator-plane samples back before the BEM update."""
        target = windows_path_to_wsl(case_dir / "postProcessing",
                                     config.tools.wsl_mount_root)
        source = wsl_case + "/postProcessing/actuatorDisk"
        probe_target = target + "/actuatorDisk"
        command = (f"mkdir -p {shlex.quote(probe_target)} && "
                   f"cp -a {shlex.quote(source + '/.')} {shlex.quote(probe_target + '/')}")
        self._run_openfoam(config, None, command, log)

    def _sync_case_from_wsl(self, config: ProjectConfig, wsl_case: str,
                            case_dir: Path, log: Path) -> None:
        """Copy the completed mesh or solver state into the project candidate."""
        target = windows_path_to_wsl(case_dir, config.tools.wsl_mount_root)
        command = (f"mkdir -p {shlex.quote(target)} && "
                   f"cp -a {shlex.quote(wsl_case + '/.')} {shlex.quote(target + '/')}")
        self._run_openfoam(config, None, command, log)

    def _cleanup_wsl_case(self, config: ProjectConfig, wsl_case: str, log: Path) -> None:
        """Remove the unique WSL scratch copy after its full state is saved."""
        root = config.tools.wsl_work_root.strip().rstrip("/")
        if not wsl_case.startswith(root + "/run_"):
            raise ValueError("Refusing to remove an OpenFOAM scratch path outside its configured root.")
        self._run_openfoam(config, None, f"rm -rf -- {shlex.quote(wsl_case)}", log)

    def _bem_inputs(self, config: ProjectConfig, tables: Path | None = None):
        """Load per-workflow polars and apply the project's current operating point."""
        resources = Path(tables or self.resources / "cfd_tables")
        flow, turbine = load_setup(resources)
        flow.speed = config.cfd.flow_speed_m_s
        flow.density = config.cfd.density_kg_m3
        flow.viscosity = config.cfd.viscosity_pa_s
        turbine.radius = config.cfd.rotor_radius_m
        turbine.hub_radius = config.cfd.hub_radius_m
        turbine.blades = config.cfd.blades
        turbine.omega = config.cfd.omega_rad_s
        turbine.pitch = config.cfd.pitch_deg
        turbine.tip_loss_model = config.cfd.tip_loss_model
        turbine.bontempo_g_a = config.cfd.bontempo_g_a
        turbine.bontempo_g_b = config.cfd.bontempo_g_b
        turbine.bontempo_g_c = config.cfd.bontempo_g_c
        actuator_thickness = config.geometry.actuator_thickness / 1000
        blade = load_blade(resources, config.cfd.stations, thickness=actuator_thickness)
        return blade, turbine, flow, load_airfoil(resources)

    @staticmethod
    def _validate_settings(config: ProjectConfig) -> None:
        """Validate geometry, operating point, mesh, solver, and WSL settings."""
        geometry = OpenTurbineRunner._geometry_parameters(config)
        if any(abs(value) > 1e-9 for value in (
            geometry.domain_origin_r, geometry.resolution_origin_r, geometry.hub_origin_r,
        )):
            raise ValueError("OpenFOAM wedge geometry requires the domain, resolution region, and hub axis at r=0.")
        if not math.isclose(geometry.hub_radius / 1000, config.cfd.hub_radius_m, abs_tol=1e-6):
            raise ValueError("Match Geometry / Hub radius to CFD / BEM / Rotor hub radius for the OpenFOAM workflow.")
        if not math.isclose(
            (geometry.hub_radius + geometry.actuator_radial_span) / 1000,
            config.cfd.rotor_radius_m, abs_tol=1e-6,
        ):
            raise ValueError("Match the OpenFOAM geometry actuator outer radius to CFD / BEM / Rotor radius.")
        if config.cfd.max_outer_iterations < 1 or config.cfd.fluent_iterations < 1:
            raise ValueError("OpenFOAM iteration limits must be positive integers.")
        if config.cfd.stations < 2 or config.cfd.flow_speed_m_s <= 0 or config.cfd.omega_rad_s <= 0:
            raise ValueError("OpenFOAM/BEM requires at least two stations and positive wind and rotor speeds.")
        if min(config.mesh.global_size_cm, config.mesh.resolution_size_cm,
               config.mesh.hub_size_cm) <= 0:
            raise ValueError("OpenFOAM global, resolution, and hub mesh sizes must be positive.")
        if (config.openfoam.max_global_cells < 1000 or config.openfoam.solver_tolerance <= 0
                or not 0 < config.openfoam.solver_relaxation <= 1
                or not 0 < config.openfoam.turbulence_intensity < 1
                or not 0 < config.openfoam.wedge_angle_deg <= 15):
            raise ValueError("OpenFOAM solver and wedge settings are outside their supported ranges.")
        if config.cfd.viscous_model not in {"k_epsilon", "k_omega", "spalart_allmaras"}:
            raise ValueError("Select k-epsilon, k-omega, or Spalart-Allmaras for OpenFOAM turbulence.")
        require_executable(config.tools.freecad, "FreeCAD")
        require_executable(config.tools.wsl_executable, "WSL")
        if not config.tools.wsl_distribution.strip():
            raise ValueError("Set the WSL distribution name on the Project tab.")
        if not config.tools.openfoam_bashrc.startswith("/"):
            raise ValueError("Set the OpenFOAM bashrc to an absolute WSL path.")
        if (not config.tools.wsl_mount_root.startswith("/")
                or not config.tools.wsl_work_root.startswith("/")
                or re.search(r"\s", config.tools.wsl_work_root)):
            raise ValueError("Set absolute WSL mount and scratch paths; the OpenFOAM scratch path cannot contain spaces.")

    def _validate_resources(self) -> None:
        """Reject missing BEM tables before launching FreeCAD."""
        missing = [name for name in (
            "metadata.json", "ntnu_geometry.csv", "s826_alpha.csv", "s826_re.csv",
            "s826_cl.csv", "s826_cd.csv",
        ) if not (self.resources / "cfd_tables" / name).is_file()]
        if missing:
            raise FileNotFoundError("OpenFOAM workflow CFD tables are missing: " + ", ".join(missing))

    @staticmethod
    def _candidate_metadata(config: ProjectConfig, geometry: OpenTurbineParameters) -> dict:
        """Record only inputs needed to reproduce this OpenFOAM candidate."""
        configuration = config.to_dict()
        configuration.pop("ga", None)
        configuration.pop("design_variables", None)
        configuration["geometry"] = asdict(geometry)
        configuration["mesh"] = {
            name: getattr(config.mesh, name)
            for name in ("global_size_cm", "resolution_size_cm", "hub_size_cm")
        }
        configuration["tools"] = {
            name: getattr(config.tools, name)
            for name in ("freecad", "wsl_executable", "wsl_distribution",
                         "openfoam_bashrc", "wsl_mount_root", "wsl_work_root")
        }
        return {
            "workflow_id": WORKFLOW_ID,
            "configuration": configuration,
            "geometry": asdict(geometry),
            "mesh": configuration["mesh"],
            "cfd": asdict(config.cfd),
            "openfoam": asdict(config.openfoam),
        }

    @staticmethod
    def _read_probes(case_dir: Path, expected: int) -> list[tuple[float, float, float]]:
        """Read the newest actuator-plane U sample from OpenFOAM probes output."""
        root = Path(case_dir) / "postProcessing" / "actuatorDisk"
        files = list(root.rglob("U")) if root.exists() else []
        if not files:
            raise FileNotFoundError("OpenFOAM did not write actuator-plane probes for U.")
        vectors = None
        for path in sorted(files, key=lambda item: item.stat().st_mtime):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                found = _VECTOR.findall(line)
                if len(found) == expected:
                    vectors = [tuple(map(float, vector)) for vector in found]
        if vectors is None:
            raise ValueError(f"OpenFOAM probes did not contain {expected} velocity vectors.")
        if any(not all(math.isfinite(value) for value in vector) for vector in vectors):
            raise ValueError("OpenFOAM actuator-plane probes contain non-finite velocities.")
        return vectors

    @staticmethod
    def _latest_time(case_dir: Path) -> float:
        """Find the newest numeric OpenFOAM time directory."""
        times = []
        for item in Path(case_dir).iterdir():
            if item.is_dir():
                try:
                    value = float(item.name)
                except ValueError:
                    continue
                if math.isfinite(value):
                    times.append(value)
        if not times:
            raise RuntimeError("OpenFOAM case has no initial or converged time directory.")
        return max(times)

    @staticmethod
    def _cell_count(log: Path) -> int | None:
        """Read the final cell count reported by checkMesh."""
        try:
            text = Path(log).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        matches = re.findall(r"(?m)^\s*cells:\s*(\d+)", text)
        return int(matches[-1]) if matches else None

    @staticmethod
    def _validate_mesh_quality(log: Path) -> None:
        """Stop before CFD if checkMesh reports failed geometry/topology checks."""
        text = Path(log).read_text(encoding="utf-8", errors="replace")
        failures = re.findall(r"(?m)^Failed\s+(\d+)\s+mesh checks\.$", text)
        if failures and int(failures[-1]) > 0:
            raise RuntimeError(
                f"OpenFOAM checkMesh reported {failures[-1]} failed checks; inspect {log}."
            )
        if "Mesh OK." not in text:
            raise RuntimeError(f"OpenFOAM checkMesh did not confirm a valid mesh; inspect {log}.")

    @staticmethod
    def _zone_counts(path: Path) -> dict[str, int]:
        """Read the cell-label count for each generated rotor cellZone."""
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        pattern = re.compile(
            r"(rotorBand\d+)\s*\{.*?cellLabels\s+List<label>\s+(\d+)", re.S)
        return {name: int(count) for name, count in pattern.findall(text)}

    @staticmethod
    def _keep_latest_solution(case_dir: Path) -> None:
        """Keep the initial fields and latest converged solution only."""
        latest = OpenFoamOpenTurbineRunner._latest_time(case_dir)
        for item in Path(case_dir).iterdir():
            if not item.is_dir():
                continue
            try:
                value = float(item.name)
            except ValueError:
                continue
            if value not in {0.0, latest}:
                shutil.rmtree(item)
