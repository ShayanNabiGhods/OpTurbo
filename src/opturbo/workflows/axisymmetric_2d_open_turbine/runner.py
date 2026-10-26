"""FreeCAD-only candidate pipeline for open-turbine STEP handoff."""

from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
from typing import Callable

from ...models import ProjectConfig
from ...pipeline.process import require_executable, run_streaming
from ...storage import atomic_json
from .geometry.parameters import OUTPUT_NAMES, OpenTurbineParameters
from .geometry.validation import validate_parameters


class OpenTurbineRunner:
    """Generate geometry and hand off a unique STEP assembly to the user."""

    geometry_only = True

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
