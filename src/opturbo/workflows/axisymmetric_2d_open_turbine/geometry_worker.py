"""Run the open-turbine STEP builder inside the configured FreeCAD runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

APPLICATION_ROOT = (Path(__file__).resolve().parents[4]
                    if "__file__" in globals() else Path.cwd().resolve())
WORKER_PATH = (APPLICATION_ROOT / "src" / "opturbo" / "workflows"
               / "axisymmetric_2d_open_turbine" / "geometry_worker.py")
sys.path.insert(0, str(APPLICATION_ROOT / "src"))

from opturbo.workflows.axisymmetric_2d.geometry_worker import run_with_freecad
from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.parameters import OpenTurbineParameters


def main() -> None:
    """Load open-turbine dimensions, export all STEP files, and report them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="STEP output folder")
    parser.add_argument("--config", required=True, help="JSON file with open-turbine dimensions")
    parser.add_argument("--freecad", required=True, help="FreeCAD command-line executable")
    args = parser.parse_args()
    try:
        from opturbo.workflows.axisymmetric_2d_open_turbine.geometry.build_case import build_open_case
    except ModuleNotFoundError as error:
        if error.name not in {"FreeCAD", "Part"}:
            raise
        run_with_freecad(args.freecad, WORKER_PATH)
        return
    parameters = OpenTurbineParameters(**json.loads(Path(args.config).read_text(encoding="utf-8")))
    for path in build_open_case(parameters, Path(args.out)):
        print(f"Created: {path}")


if __name__ == "__main__":
    main()
