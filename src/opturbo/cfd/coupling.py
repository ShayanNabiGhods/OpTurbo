"""High-level persistent CFD/BEM coupling workflow."""

import math
import json
import shutil
from pathlib import Path
from .bem import performance, solve, sources_from
from .fluent import run, write_journal
from .reports import read_report


def initial_sources(blade):
    """Create the current smooth startup source field."""
    axial, tangential = [], []
    for radius in blade.radius:
        mu = (radius - 0.045) / (0.45 - 0.045)
        axial.append(-10000 * math.sin(math.pi * mu) ** 2)
        tangential.append(1000.0)
    return axial, tangential


def relax(old, new, fraction):
    """Blend old and new source values."""
    return [(1 - fraction) * a + fraction * b for a, b in zip(old, new)]


def clear_report_files(workdir):
    """Remove Fluent reports so each outer iteration writes a fresh result."""
    for filename in ("axial-report.txt", "tangential-report.txt"):
        (Path(workdir) / filename).unlink(missing_ok=True)


def journal_failed(output):
    """Return whether Fluent stopped while processing the batch journal."""
    markers = (
        "Interrupting journal processing",
        "Error: An error or interrupt occurred in the previous operation.",
        "Divergence detected in AMG solver",
        "Floating point exception",
        "solution is diverging",
    )
    lowered = output.lower()
    return any(marker.lower() in lowered for marker in markers)


def run_coupling(config):
    """Run the persistent Fluent/BEM outer loop from an explicit configuration."""
    blade, flow = config["blade"], config["flow"]
    turbine, airfoil = config["turbine"], config["airfoil"]
    work, history = Path(config["workdir"]), Path(config["workdir"]) / "iteration_history"
    history.mkdir(exist_ok=True)
    axial, tangential = initial_sources(blade)
    previous_cp = 0.0
    previous_ct = 0.0
    for iteration in range(1, config["max_outer"] + 1):
        source = work / "ad_sources.dat"
        with source.open("w") as handle:
            handle.write("# r Sx Sw\n" + str(len(blade.radius)) + "\n")
            for radius, sx, st in zip(blade.radius, axial, tangential):
                handle.write(f"{radius:.10e} {sx:.10e} {st:.10e}\n")
        shutil.copyfile(source, history / f"ad_sources_iter{iteration:02d}.dat")
        journal = work / "run_ad.jou"
        write_journal(journal, blade, iteration == 1, iteration,
                      config.get("mesh_name", "axisymmetric_mesh.msh"),
                      config.get("fluent_iterations", 200))
        clear_report_files(work)
        status, output = run(config["fluent"], work, journal,
                             config.get("processors", 4))
        (history / f"fluent_output_iter{iteration:02d}.log").write_text(output)
        if status or journal_failed(output):
            raise RuntimeError(f"Fluent failed at outer iteration {iteration}")
        ua = read_report(work / "axial-report.txt", len(blade.radius))
        ut = read_report(work / "tangential-report.txt", len(blade.radius))
        result = solve(flow, turbine, blade, airfoil, ua, ut)
        value, new = performance(flow, turbine, blade, result), sources_from(result)
        if not math.isfinite(value.cp) or not math.isfinite(value.ct):
            raise RuntimeError(f"Non-finite CFD/BEM result at outer iteration {iteration}")
        result_data = {
            "iteration": iteration, "cp": value.cp, "ct": value.ct,
            "thrust": value.thrust, "torque": value.torque, "power": value.power,
            "a": result.a, "a_prime": result.ap, "phi_deg": result.phi,
            "alpha_deg": result.alpha, "reynolds": result.reynolds,
            "prandtl_loss": result.loss, "radius_m": blade.radius,
        }
        (history / f"bem_results_iter{iteration:02d}.json").write_text(
            json.dumps(result_data, indent=2), encoding="utf-8")
        (work / "latest_result.json").write_text(
            json.dumps(result_data, indent=2), encoding="utf-8")
        axial, tangential = relax(axial, new.axial, config["relax"]), relax(tangential, new.tangential, config["relax"])
        print(f"outer {iteration:02d}: Cp={value.cp:.6f}")
        print(f"outer {iteration:02d}: Ct={value.ct:.6f}")
        if max(abs(value.cp - previous_cp), abs(value.ct - previous_ct)) < config["tolerance"]:
            break
        previous_cp = value.cp
        previous_ct = value.ct
    if not config.get("keep_iteration_data", True):
        for solution in work.glob("coupled_solution_*.dat.h5"):
            solution.unlink(missing_ok=True)
    return value
