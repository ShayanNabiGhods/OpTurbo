"""FreeCAD adapter for generating the candidate STEP assembly."""

from dataclasses import asdict
import json
from pathlib import Path
import sys

from .....models import GeometrySettings, ProjectConfig
from opturbo.pipeline.process import require_executable, run_streaming
from .base import PipelineStage


class FreeCADGeometryStage(PipelineStage):
    """Run the FreeCAD worker and verify its STEP output."""

    def run(self, config: ProjectConfig, geometry: GeometrySettings,
                  parsec: dict, output: Path) -> Path:
        self.runner.emit("[1/4] Generating FreeCAD STEP profiles")
        settings = asdict(geometry)
        settings["parsec"] = parsec
        if geometry.design_type == "flanged":
            settings["flanged_curve"] = parsec["lower"]
        settings_path = output / "geometry_settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        script = (
            self.runner.root / "src" / "opturbo" / "workflows"
            / "axisymmetric_2d" / "geometry_worker.py"
        )
        command = [sys.executable, str(script), "--config", str(settings_path), "--out", str(output),
                   "--freecad", require_executable(config.tools.freecad, "FreeCAD")]
        run_streaming(command, self.runner.root, output / "freecad.log", self.runner.emit, self.runner.cancel)
        assembly = output / "profile_assembly.step"
        if not assembly.exists():
            raise FileNotFoundError(f"FreeCAD did not create {assembly}")
        return assembly
