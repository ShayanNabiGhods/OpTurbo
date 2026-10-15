"""High-level persistent CFD/BEM coupling workflow."""

import math
import json
import shutil
from pathlib import Path
from .bem import performance, solve, sources_from
from .fluent import run, write_journal
from .reports import read_report


def initial_sources(blade):
    """Create a smooth startup field with thickness-independent integrated load."""
    axial, tangential = [], []
    thickness_scale = 0.005 / blade.thickness
    for radius in blade.radius:
        mu = (radius - 0.045) / (0.45 - 0.045)
        axial.append(-10000 * thickness_scale * math.sin(math.pi * mu) ** 2)
        tangential.append(1000.0 * thickness_scale)
    return axial, tangential


def relax(old, new, fraction):
    """Blend old and new source values."""
    return [(1 - fraction) * a + fraction * b for a, b in zip(old, new)]


def clear_report_files(workdir):
    """Remove Fluent reports so each outer iteration writes a fresh result."""
    for filename in ("axial-report.txt", "tangential-report.txt"):
        (Path(workdir) / filename).unlink(missing_ok=True)


def load_source_terms(path, blade):
    """Load a compatible source field from a previous successful candidate."""
    try:
        rows = [line.split() for line in Path(path).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
        count = int(rows[0][0])
        data = rows[1:]
        if count != len(blade.radius) or len(data) != count:
            return None
        radii, axial, tangential = [], [], []
        for row in data:
            if len(row) != 3:
                return None
            radius, sx, st = map(float, row)
            radii.append(radius)
            axial.append(sx)
            tangential.append(st)
        if any(not all(math.isfinite(value) for value in values)
               for values in (radii, axial, tangential)):
            return None
        if any(abs(a - b) > 1e-8 for a, b in zip(radii, blade.radius)):
            return None
        return axial, tangential
    except (OSError, ValueError, IndexError):
        return None


def write_source_terms(path, blade, axial, tangential):
    """Save a source field in the UDF input format for reuse by the next candidate."""
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write("# r Sx Sw\n" + str(len(blade.radius)) + "\n")
        for radius, sx, st in zip(blade.radius, axial, tangential):
            handle.write(f"{radius:.10e} {sx:.10e} {st:.10e}\n")


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
    seed_path = config.get("previous_candidate_source_path")
    source_initialization = config.get("source_initialization", "conservative")
    seeded = load_source_terms(seed_path, blade) if (
        source_initialization == "previous_candidate" and seed_path
    ) else None
    if seeded is not None:
        conservative_axial, conservative_tangential = initial_sources(blade)
        weight = float(config.get("previous_source_weight", 1.0))
        if not math.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("Previous-source weight must be a number from 0 to 1.")
        axial = relax(conservative_axial, seeded[0], weight)
        tangential = relax(conservative_tangential, seeded[1], weight)
        print(f"Using previous-candidate actuator sources with weight {weight:.3g}.")
    else:
        axial, tangential = initial_sources(blade)
        if source_initialization == "previous_candidate":
            print("No compatible previous-candidate sources found; using conservative initialization.")
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
                      config.get("fluent_iterations", 200),
                      config.get("fluent_settings", {}))
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
            "actuator_thickness_m": blade.thickness,
            "a": result.a, "a_prime": result.ap, "phi_deg": result.phi,
            "alpha_deg": result.alpha, "reynolds": result.reynolds,
            "loss_factor": result.loss, "tip_loss_model": turbine.tip_loss_model,
            "radius_m": blade.radius,
        }
        if turbine.tip_loss_model == "prandtl":
            result_data["prandtl_loss"] = result.loss
        (history / f"bem_results_iter{iteration:02d}.json").write_text(
            json.dumps(result_data, indent=2), encoding="utf-8")
        (work / "latest_result.json").write_text(
            json.dumps(result_data, indent=2), encoding="utf-8")
        axial, tangential = relax(axial, new.axial, config["relax"]), relax(tangential, new.tangential, config["relax"])
        write_source_terms(work / "final_ad_sources.dat", blade, axial, tangential)
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
