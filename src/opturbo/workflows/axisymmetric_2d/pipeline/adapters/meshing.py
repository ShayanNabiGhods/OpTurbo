"""ANSYS Workbench and Meshing adapter for the axisymmetric workflow."""

from pathlib import Path
import shutil
import sys
import time

from .....models import ProjectConfig
from opturbo.pipeline.process import require_executable, run_streaming, windows_path
from .base import PipelineStage


class AnsysMeshingStage(PipelineStage):
    """Prepare and run the candidate-specific ANSYS meshing project."""

    def run(self, config: ProjectConfig, scdoc: Path, output: Path) -> Path:
        self.runner.emit("[3/4] Generating the ANSYS mesh")
        source = self.runner.resources / "meshing"
        shutil.copy2(source / "mesh_script.py", output / "mesh_script.py")
        mesh_script = (output / "mesh_script.py").read_text(encoding="utf-8")
        replacements = {
            # Geometry values used for body selection
            "DOMAIN_HEIGHT_CM = 675.0": f"DOMAIN_HEIGHT_CM = {config.geometry.domain_height / 10.0}",
            "HUB_RADIUS_CM = 4.5": f"HUB_RADIUS_CM = {config.geometry.hub_radius / 10.0}",
            "DOMAIN_ORIGIN_X_CM = -225.0": f"DOMAIN_ORIGIN_X_CM = {config.geometry.domain_origin_x / 10.0}",
            "DOMAIN_LENGTH_CM = 900.0": f"DOMAIN_LENGTH_CM = {config.geometry.domain_length / 10.0}",
            "DUCT_ORIGIN_X_CM = -2.45": f"DUCT_ORIGIN_X_CM = {config.geometry.duct_origin_x / 10.0}",
            "DUCT_ORIGIN_R_CM = 46.95": f"DUCT_ORIGIN_R_CM = {config.geometry.duct_origin_r / 10.0}",
            "DUCT_CHORD_CM = 9.0": f"DUCT_CHORD_CM = {config.geometry.duct_chord / 10.0}",
            "DUCT_ANGLE_DEG = 0.0": f"DUCT_ANGLE_DEG = {config.geometry.duct_angle_deg}",
            "RESOLUTION_LENGTH = 270.0": f"RESOLUTION_LENGTH = {config.geometry.resolution_length / 10}",
            "RESOLUTION_INLET_RADIUS = 90.0": f"RESOLUTION_INLET_RADIUS = {config.geometry.resolution_inlet_radius / 10}",
            # Additional geometry values for flanged mode
            "DUCT_FLANGE_LENGTH = 9.0": (
                f"DUCT_FLANGE_LENGTH = {config.geometry.duct_flange_length / 10.0}"
                if config.geometry.design_type == "flanged"
                else "DUCT_FLANGE_LENGTH = 0"
            ),
            "DUCT_FLANGE_ANGLE_DEG = 85.0": (
                f"DUCT_FLANGE_ANGLE_DEG = {config.geometry.duct_flange_angle_deg}"
                if config.geometry.design_type == "flanged"
                else "DUCT_FLANGE_ANGLE_DEG = 0"
            ),
            "LOWER_TRAILING_EDGE_HEIGHT = 0.1": (
                "LOWER_TRAILING_EDGE_HEIGHT = " + str(next(
                    item.value for item in config.design_variables
                    if item.key == "lower.trailing_edge_height"
                ))
            ),
            "DUCT_THICKNESS = 0.1": (
                f"DUCT_THICKNESS = {config.geometry.duct_thickness / 10.0}"
                if config.geometry.design_type == "flanged"
                else "DUCT_THICKNESS = 0"
            ),

            # Meshing sizes and properties
            "GLOBAL_SIZE_CM = 3.0": f"GLOBAL_SIZE_CM = {config.mesh.global_size_cm}",
            "GROWTH_RATE = 1.1": f"GROWTH_RATE = {config.mesh.growth_rate}",
            "CPU_CORES_FOR_PARALLEL_PART_MESHING = None": (
                f"CPU_CORES_FOR_PARALLEL_PART_MESHING = {config.mesh.cpu_cores}"
            ),
            'MESH_METHOD = "Quad"': f'MESH_METHOD = {config.mesh.method!r}',
            "CURVATURE_ANGLE_DEG = 5.0": f"CURVATURE_ANGLE_DEG = {config.mesh.curvature_angle_deg}",
            "RESOLUTION_SIZE_CM = 1.0": f"RESOLUTION_SIZE_CM = {config.mesh.resolution_size_cm}",
            "DUCT_SIZE_CM = 0.3": f"DUCT_SIZE_CM = {config.mesh.duct_size_cm}",
            "HUB_SIZE_CM = 0.3": f"HUB_SIZE_CM = {config.mesh.hub_size_cm}",
            "INFLATION_ENABLED = True": f"INFLATION_ENABLED = {config.mesh.inflation_enabled!r}",
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
        journal_text = self.workbench_journal(staged_scdoc, staged_script, project)
        (output / "run_meshing.wbjn").write_text(journal_text, encoding="utf-8")
        staged_journal.write_text(journal_text, encoding="utf-8")
        workbench_command = [require_executable(config.tools.workbench, "ANSYS Workbench"), "-B", "-R",
                             windows_path(staged_journal)]
        try:
            run_streaming(workbench_command, stage, output / "meshing.log", self.runner.emit, self.runner.cancel)
        except RuntimeError:
            self.runner.emit("Workbench failed once; clearing its fixed scratch project and retrying.")
            project.unlink(missing_ok=True)
            if project_files.exists():
                shutil.rmtree(project_files)
            time.sleep(3)
            run_streaming(workbench_command, stage, output / "meshing.log", self.runner.emit, self.runner.cancel)
        extractor = source / "extract_mesh_artifact.py"
        mesh = output / "axisymmetric_mesh.msh"
        run_streaming([sys.executable, str(extractor), "--project", str(project), "--output", str(mesh), "--cleanup"],
                      output, output / "meshing.log", self.runner.emit, self.runner.cancel)
        candidates = list(output.glob("axisymmetric_mesh.msh*"))
        if not candidates:
            raise FileNotFoundError("ANSYS Meshing produced no Fluent mesh artifact.")
        return candidates[0]

    @staticmethod
    def workbench_journal(scdoc: Path, mesh_script: Path, project: Path) -> str:
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
