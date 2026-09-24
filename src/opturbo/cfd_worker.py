"""Prepare or run the persistent Fluent/BEM Python workflow."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
APPLICATION_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APPLICATION_ROOT / "src"))

from opturbo.cfd.coupling import run_coupling
from opturbo.cfd.resources import load_airfoil, load_blade, load_setup


def build_config(resources, workdir, stations, max_outer=15):
    """Build the beginner-readable configuration used by the outer loop."""
    resources = Path(resources)
    flow, turbine = load_setup(resources)
    return {
        "blade": load_blade(resources, stations=stations),
        "flow": flow,
        "turbine": turbine,
        "airfoil": load_airfoil(resources),
        "workdir": Path(workdir),
        "fluent": os.environ.get(
            "FLUENT_EXECUTABLE",
            r"C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe",
        ),
        "max_outer": max_outer,
        "tolerance": 1e-3,
        "relax": 0.3,
    }


def main():
    """Print the setup, and run Fluent only when explicitly requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=int, default=36,
                        help="number of blade stations (default: 36)")
    parser.add_argument("--run-fluent", action="store_true",
                        help="start Fluent and run the persistent outer loop")
    parser.add_argument("--max-outer", type=int, default=15,
                        help="maximum outer iterations (default: 15)")
    parser.add_argument("--config", help="optional OpTurbo CFD JSON settings")
    parser.add_argument("--mesh", help="mesh file copied into the Fluent folder")
    parser.add_argument("--resources", required=True, help="folder containing BEM CSV/JSON tables")
    parser.add_argument("--workdir", required=True, help="candidate Fluent working folder")
    args = parser.parse_args()

    config = build_config(args.resources, args.workdir, args.stations, args.max_outer)
    if args.config:
        settings = json.loads(Path(args.config).read_text(encoding="utf-8"))
        config.update(settings)
        flow = config["flow"]
        turbine = config["turbine"]
        flow.speed = settings.get("flow_speed_m_s", flow.speed)
        flow.density = settings.get("density_kg_m3", flow.density)
        flow.viscosity = settings.get("viscosity_pa_s", flow.viscosity)
        turbine.radius = settings.get("rotor_radius_m", turbine.radius)
        turbine.hub_radius = settings.get("hub_radius_m", turbine.hub_radius)
        turbine.blades = settings.get("blades", turbine.blades)
        turbine.omega = settings.get("omega_rad_s", turbine.omega)
        turbine.pitch = settings.get("pitch_deg", turbine.pitch)
    if args.mesh:
        source = Path(args.mesh)
        target = config["workdir"] / "axisymmetric_mesh.msh"
        shutil.copy2(source, target)
        config["mesh_name"] = target.name
    print(f"Prepared {args.stations}-station Python BEM setup.")
    print(f"Fluent resources: {config['workdir']}")
    if args.run_fluent:
        result = run_coupling(config)
        print(f"OPTURBO_RESULT Cp={result.cp:.10g} Ct={result.ct:.10g}")
    else:
        print("Use --run-fluent to start the CFD coupling.")


if __name__ == "__main__":
    main()
