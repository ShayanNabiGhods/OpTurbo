"""Create the DAWT STEP profiles with FreeCAD's Python interpreter."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

FREECAD_COMMAND = Path(r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
WSL_FREECAD_COMMAND = Path("/mnt/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe")
APPLICATION_ROOT = (
    Path(__file__).resolve().parents[2]
    if "__file__" in globals()
    else Path.cwd().resolve()
)
sys.path.insert(0, str(APPLICATION_ROOT / "src"))

from opturbo.geometry.config import DesignParameters


def parse_arguments() -> argparse.Namespace:
    """Read command-line options for the output folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="output", help="STEP output folder")
    parser.add_argument("--config", help="JSON file containing geometry and PARSEC settings")
    return parser.parse_args()


def main() -> None:
    """Validate dimensions, build the profiles, and print output paths."""
    try:
        from opturbo.geometry.build_case import build_case
    except ModuleNotFoundError as error:
        if error.name in {"FreeCAD", "Part"}:
            run_with_freecad()
            return
        raise
    args = parse_arguments()
    parameters = DesignParameters()
    if args.config:
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        parameters = DesignParameters(**data)
    paths = build_case(parameters, Path(args.out).resolve())
    for path in paths:
        print(f"Created: {path}")


def run_with_freecad() -> None:
    """Relaunch this script and explicitly execute it inside FreeCAD."""
    command_path = WSL_FREECAD_COMMAND if os.name != "nt" else FREECAD_COMMAND
    if not command_path.exists():
        raise SystemExit(f"FreeCAD was not found at: {FREECAD_COMMAND}")

    script_path = Path(__file__).resolve()
    script_text = str(script_path)
    if os.name != "nt" and script_text.startswith("/mnt/c/"):
        script_text = "C:/" + script_text[len("/mnt/c/"):]
    script_text = script_text.replace("\\", "/")
    arguments = ["run.py"]
    for argument in sys.argv[1:]:
        if os.name != "nt" and argument.startswith("/mnt/"):
            argument = argument[5].upper() + ":/" + argument[7:]
        arguments.append(argument.replace("\\", "/"))
    freecad_code = (
        "import sys; "
        f"sys.argv = {arguments!r}; "
        f"exec(compile(open({script_text!r}, encoding='utf-8').read(), "
        f"{script_text!r}, 'exec'))"
    )
    command = [str(command_path), "-c", freecad_code]
    subprocess.run(command, cwd=APPLICATION_ROOT, check=True)


if __name__ == "__main__":
    main()
