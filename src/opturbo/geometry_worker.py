"""Compatibility entry point for the axisymmetric FreeCAD worker."""

import sys
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APPLICATION_ROOT / "src"))

from opturbo.workflows.axisymmetric_2d.geometry_worker import (
    APPLICATION_ROOT,
    FREECAD_COMMAND,
    main,
    parse_arguments,
    run_with_freecad,
)

if __name__ == "__main__":
    main()
