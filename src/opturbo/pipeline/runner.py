"""Sequential candidate pipeline: STEP, SCDOC, mesh, then CFD/BEM."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
import json
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Callable

from ..models import GeometrySettings, ProjectConfig, VariableSpec
from ..parsec import nested_parameters, validate_lower_profile, validate_profile
from .process import executable_path, run_streaming, windows_path
from ..storage import atomic_json


@dataclass
class PreparedCandidate:
    """Candidate-owned inputs retained after the shared CAD/meshing stages."""

    config: ProjectConfig
    folder: Path
    mesh: Path


class PipelineRunner:
    """Run one design through the four isolated engineering adapters."""

    def __init__(self, application_root: Path, emit: Callable[[str], None] = print):
        self.root = Path(application_root)
        self.resources = self.root / "resources"
        self.emit = emit

    def evaluate(self, config: ProjectConfig, genome: dict[str, float], candidate_dir: Path) -> dict:
        """Evaluate one genome and return Cp, Ct, and saved artifact paths."""
        return self.finish(self.prepare(config, genome, candidate_dir))

    def prepare(self, config: ProjectConfig, genome: dict[str, float], candidate_dir: Path) -> PreparedCandidate:
        """Run stages 1–3 serially and copy the mesh out of the shared handoff."""
        if config.cfd.tip_loss_model not in {"prandtl", "bontempo2025"}:
            raise ValueError("Choose a valid tip-loss correction model.")
        variables = [replace(item, value=genome.get(item.key, item.value) if item.optimize else item.value)
                     for item in config.design_variables]
        geometry_overrides = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        geometry = replace(config.geometry, **geometry_overrides)
        config = replace(config, geometry=geometry, design_variables=variables)
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
        if not math.isfinite(float(result["cp"])) or not math.isfinite(float(result["ct"])):
            raise ValueError("CFD returned a non-finite Cp or Ct.")
        result["candidate_dir"] = str(prepared.folder)
        atomic_json(prepared.folder / "result.json", result)
        return result

    def _geometry(self, config: ProjectConfig, geometry: GeometrySettings,
                  parsec: dict, output: Path) -> Path:
        self.emit("[1/4] Generating FreeCAD STEP profiles")
        settings = asdict(geometry)
        settings["parsec"] = parsec
        settings_path = output / "geometry_settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        script = self.root / "src" / "opturbo" / "geometry_worker.py"
        command = [sys.executable, str(script), "--config", str(settings_path), "--out", str(output)]
        run_streaming(command, self.root, output / "freecad.log", self.emit)
        assembly = output / "profile_assembly.step"
        if not assembly.exists():
            raise FileNotFoundError(f"FreeCAD did not create {assembly}")
        return assembly

    def _spaceclaim(self, config: ProjectConfig, assembly: Path, output: Path) -> Path:
        self.emit("[2/4] Running the fixed SpaceClaim script")
        handoff = Path(config.tools.handoff_dir)
        if sys.platform != "win32" and str(handoff).startswith("C:\\"):
            handoff = Path("/mnt/c") / str(handoff)[3:].replace("\\", "/")
        handoff.mkdir(parents=True, exist_ok=True)
        fixed_step = handoff / "profile_assembly.step"
        fixed_scdoc = handoff / "profile_assembly.scdoc"
        shutil.copy2(assembly, fixed_step)
        fixed_scdoc.unlink(missing_ok=True)
        script = self.resources / "spaceclaim" / "profile_assembly.scscript"
        command = [executable_path(config.tools.spaceclaim), "/Headless=True",
                   f"/RunScript={windows_path(script)}", "/ExitAfterScript=True"]
        run_streaming(command, self.root, output / "spaceclaim.log", self.emit)
        if not fixed_scdoc.exists():
            raise FileNotFoundError("SpaceClaim did not create profile_assembly.scdoc in its fixed handoff folder.")
        destination = output / "profile_assembly.scdoc"
        shutil.copy2(fixed_scdoc, destination)
        return destination

    def _mesh(self, config: ProjectConfig, scdoc: Path, output: Path) -> Path:
        self.emit("[3/4] Generating the ANSYS mesh")
        source = self.resources / "meshing"
        shutil.copy2(source / "mesh_script.py", output / "mesh_script.py")
        mesh_script = (output / "mesh_script.py").read_text(encoding="utf-8")
        replacements = {
            # Geometry values used for body selection
            "DOMAIN_HEIGHT_CM = 675.0": f"DOMAIN_HEIGHT_CM = {config.geometry.domain_height / 10.0}",
            "HUB_RADIUS_CM = 4.5": f"HUB_RADIUS_CM = {config.geometry.hub_radius / 10.0}",
            "DOMAIN_ORIGIN_X_CM = -225.0": f"DOMAIN_ORIGIN_X_CM = {config.geometry.domain_origin_x / 10.0}",
            "DOMAIN_LENGTH_CM = 900.0": f"DOMAIN_LENGTH_CM = {config.geometry.domain_length / 10.0}",
            "DUCT_ORIGIN_X_CM = -7.2": f"DUCT_ORIGIN_X_CM = {config.geometry.duct_origin_x / 10.0}",
            "DUCT_ORIGIN_R_CM = 47.5": f"DUCT_ORIGIN_R_CM = {config.geometry.duct_origin_r / 10.0}",
            "DUCT_CHORD_CM = 20.0": f"DUCT_CHORD_CM = {config.geometry.duct_chord / 10.0}",
            "DUCT_ANGLE_DEG = 0.0": f"DUCT_ANGLE_DEG = {config.geometry.duct_angle_deg}",
            "RESOLUTION_LENGTH = 270.0": f"RESOLUTION_LENGTH = {config.geometry.resolution_length / 10}",
            "RESOLUTION_INLET_RADIUS = 90.0": f"RESOLUTION_INLET_RADIUS = {config.geometry.resolution_inlet_radius / 10}",
            
            "DUCT_FLANGE_LENGTH = 0": (
                f"DUCT_FLANGE_LENGTH = {config.geometry.duct_flange_length / 10.0}"
                if config.geometry.design_type == "flanged"
                else "DUCT_FLANGE_LENGTH = 0"
            ),
            "DUCT_FLANGE_ANGLE_DEG = 0": (
                f"DUCT_FLANGE_ANGLE_DEG = {config.geometry.duct_flange_angle_deg}"
                if config.geometry.design_type == "flanged"
                else "DUCT_FLANGE_ANGLE_DEG = 0"
            ),
            
            # Meshing sizes and properties
            "GLOBAL_SIZE_CM = 5.0": f"GLOBAL_SIZE_CM = {config.mesh.global_size_cm}",
            "CURVATURE_ANGLE_DEG = 6.0": f"CURVATURE_ANGLE_DEG = {config.mesh.curvature_angle_deg}",
            "RESOLUTION_SIZE_CM = 0.5": f"RESOLUTION_SIZE_CM = {config.mesh.resolution_size_cm}",
            "DUCT_SIZE_CM = 0.3": f"DUCT_SIZE_CM = {config.mesh.duct_size_cm}",
            "HUB_SIZE_CM = 0.5": f"HUB_SIZE_CM = {config.mesh.hub_size_cm}",
            "INFLATION_LAYERS = 5": f"INFLATION_LAYERS = {config.mesh.inflation_layers}",
            "INFLATION_MAX_THICKNESS_CM = 0.2": f"INFLATION_MAX_THICKNESS_CM = {config.mesh.inflation_max_thickness_cm}",
        }
        for old, new in replacements.items():
            mesh_script = mesh_script.replace(old, new)
        (output / "mesh_script.py").write_text(mesh_script, encoding="utf-8")
        handoff = Path(config.tools.handoff_dir)
        if sys.platform != "win32" and str(handoff).startswith("C:\\"):
            handoff = Path("/mnt/c") / str(handoff)[3:].replace("\\", "/")
        stage = handoff / "Meshing"
        stage.mkdir(parents=True, exist_ok=True)
        project = stage / "mesh_handoff.wbpj"
        project_files = stage / "mesh_handoff_files"
        project.unlink(missing_ok=True)
        if project_files.exists():
            shutil.rmtree(project_files)
        staged_scdoc = stage / "profile_assembly.scdoc"
        staged_script = stage / "mesh_script.py"
        staged_journal = stage / "run_meshing.wbjn"
        shutil.copy2(scdoc, staged_scdoc)
        shutil.copy2(output / "mesh_script.py", staged_script)
        journal_text = self._workbench_journal(staged_scdoc, staged_script, project)
        (output / "run_meshing.wbjn").write_text(journal_text, encoding="utf-8")
        staged_journal.write_text(journal_text, encoding="utf-8")
        workbench_command = [executable_path(config.tools.workbench), "-B", "-R",
                             windows_path(staged_journal)]
        try:
            run_streaming(workbench_command, stage, output / "meshing.log", self.emit)
        except RuntimeError:
            self.emit("Workbench failed once; clearing its fixed scratch project and retrying.")
            project.unlink(missing_ok=True)
            if project_files.exists():
                shutil.rmtree(project_files)
            time.sleep(3)
            run_streaming(workbench_command, stage, output / "meshing.log", self.emit)
        extractor = source / "extract_mesh_artifact.py"
        mesh = output / "axisymmetric_mesh.msh"
        run_streaming([sys.executable, str(extractor), "--project", str(project), "--output", str(mesh), "--cleanup"],
                      output, output / "meshing.log", self.emit)
        candidates = list(output.glob("axisymmetric_mesh.msh*"))
        if not candidates:
            raise FileNotFoundError("ANSYS Meshing produced no Fluent mesh artifact.")
        return candidates[0]

    @staticmethod
    def _workbench_journal(scdoc: Path, mesh_script: Path, project: Path) -> str:
        """Build a Workbench journal with candidate-specific paths."""
        return f'''# encoding: utf-8
SetScriptVersion(Version="24.2.133")
Reset()
template = GetTemplate(TemplateName="Fluid Flow")
system = template.CreateSystem()
geometry = system.GetContainer(ComponentName="Geometry")
geometry.SetFile(FilePath=r"{windows_path(scdoc)}")
mesh_component = system.GetComponent(Name="Mesh")
mesh_component.Refresh()
try:
    editor = system.GetContainer(ComponentName="Model")
except:
    editor = system.GetContainer(ComponentName="Mesh")
editor.Edit(Interactive=False)
with open(r"{windows_path(mesh_script)}", "r") as handle:
    commands = handle.read()
editor.SendCommand(Command=commands, Language="Python")
editor.Exit()
mesh_component.Update()
Save(FilePath=r"{windows_path(project)}", Overwrite=True)
'''

    def _cfd(self, config: ProjectConfig, mesh: Path, output: Path) -> dict:
        self.emit("[4/4] Running persistent Fluent/BEM coupling")
        tables = output / "resources"
        fluent_workdir = output / "fluent"
        shutil.copytree(self.resources / "cfd_tables", tables, dirs_exist_ok=True)
        shutil.copytree(self.resources / "fluent", fluent_workdir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("iteration_history", "*.log", "latest_result.json"))
        cfd_settings = {
            "fluent": executable_path(config.tools.fluent),
            "max_outer": config.cfd.max_outer_iterations,
            "tolerance": config.cfd.tolerance,
            "relax": config.cfd.relaxation,
            "fluent_iterations": config.cfd.fluent_iterations,
            "processors": config.cfd.processors,
            "flow_speed_m_s": config.cfd.flow_speed_m_s,
            "density_kg_m3": config.cfd.density_kg_m3,
            "viscosity_pa_s": config.cfd.viscosity_pa_s,
            "rotor_radius_m": config.cfd.rotor_radius_m,
            "hub_radius_m": config.cfd.hub_radius_m,
            "blades": config.cfd.blades,
            "omega_rad_s": config.cfd.omega_rad_s,
            "pitch_deg": config.cfd.pitch_deg,
            "tip_loss_model": config.cfd.tip_loss_model,
            "keep_iteration_data": config.cfd.keep_iteration_data,
            "fluent_settings": {
                "viscous_model": config.cfd.viscous_model,
                "residual_continuity": config.cfd.residual_continuity,
                "residual_x_velocity": config.cfd.residual_x_velocity,
                "residual_y_velocity": config.cfd.residual_y_velocity,
                "residual_swirl": config.cfd.residual_swirl,
                "residual_k": config.cfd.residual_k,
                "residual_epsilon": config.cfd.residual_epsilon,
                "residual_omega": config.cfd.residual_omega,
                "residual_nut": config.cfd.residual_nut,
                "gradient_scheme": config.cfd.gradient_scheme,
                "pressure_scheme": config.cfd.pressure_scheme,
                "momentum_scheme": config.cfd.momentum_scheme,
                "swirl_scheme": config.cfd.swirl_scheme,
                "k_scheme": config.cfd.k_scheme,
                "epsilon_scheme": config.cfd.epsilon_scheme,
                "omega_scheme": config.cfd.omega_scheme,
                "nut_scheme": config.cfd.nut_scheme,
                "pressure_velocity_coupling": config.cfd.pressure_velocity_coupling,
            },
        }
        settings_path = output / "cfd_settings.json"
        settings_path.write_text(json.dumps(cfd_settings, indent=2), encoding="utf-8")
        worker = self.root / "src" / "opturbo" / "cfd_worker.py"
        command = [sys.executable, str(worker), "--run-fluent",
                   "--stations", str(config.cfd.stations), "--max-outer",
                   str(config.cfd.max_outer_iterations), "--config", str(settings_path),
                   "--mesh", str(mesh), "--resources", str(tables),
                   "--workdir", str(fluent_workdir)]
        log = output / "fluent_driver.log"
        run_streaming(command, output, log, self.emit)
        latest = fluent_workdir / "latest_result.json"
        if latest.exists():
            return json.loads(latest.read_text(encoding="utf-8"))
        text = log.read_text(encoding="utf-8", errors="replace")
        match = re.findall(r"OPTURBO_RESULT Cp=([-+0-9.eE]+) Ct=([-+0-9.eE]+)", text)
        if not match:
            raise RuntimeError("Fluent finished without a readable Cp/Ct result.")
        cp, ct = match[-1]
        return {"cp": float(cp), "ct": float(ct)}
