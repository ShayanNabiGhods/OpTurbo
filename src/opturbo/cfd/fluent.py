"""Fluent journal generation and optional persistent-state execution."""

import subprocess
from pathlib import Path


VISCOUS_MODEL_COMMANDS = {
    "k_omega": "/define/models/viscous/kw-standard/yes",
    "k_epsilon": "/define/models/viscous/ke-standard/yes",
    "spalart_allmaras": "/define/models/viscous/spalart-allmaras/yes",
}
GRADIENT_RESPONSES = {
    "green_gauss_cell_based": ("no", "no"),
    "green_gauss_node_based": ("yes",),
    "least_squares_cell_based": ("no", "yes"),
}
CONVECTION_SCHEME_CODES = {
    "first_order_upwind": 0,
    "second_order_upwind": 1,
    "quick": 4,
    "third_order_muscl": 6,
}
PRESSURE_SCHEME_CODES = {
    "second_order": 12,
    "standard": 10,
    "presto": 14,
    "linear": 11,
    "body_force_weighted": 13,
}
COUPLING_SCHEME_CODES = {"simple": 20, "simplec": 21, "piso": 22, "coupled": 24}


def _require_choice(value: str, choices: dict[str, object], name: str) -> object:
    """Return a Fluent TUI value or explain which saved setting is invalid."""
    try:
        return choices[value]
    except KeyError as error:
        raise ValueError(f"Unknown Fluent {name}: {value}") from error


def _model_equations(model: str) -> tuple[str, ...]:
    """Return the residual and discretization equations active for one model."""
    equations = {
        "k_omega": ("k", "omega"),
        "k_epsilon": ("k", "epsilon"),
        "spalart_allmaras": ("nut",),
    }
    return _require_choice(model, equations, "viscous model")


def first_iteration_setup(settings: dict) -> list[str]:
    """Build model and solver commands that are valid only on outer iteration one."""
    model = settings.get("viscous_model", "k_omega")
    lines = [_require_choice(model, VISCOUS_MODEL_COMMANDS, "viscous model"), ""]
    residuals = ["continuity", "x_velocity", "y_velocity", "swirl"] + list(_model_equations(model))
    lines.append("/solve/monitors/residual/convergence-criteria")
    lines.extend(f"{float(settings.get('residual_' + name, 1e-4)):.10g}" for name in residuals)
    lines += ["", "/solve/set/gradient-scheme"]
    gradient = settings.get("gradient_scheme", "least_squares_cell_based")
    lines.extend(_require_choice(gradient, GRADIENT_RESPONSES, "gradient scheme"))
    lines += ["", "/solve/set/p-v-coupling",
              str(_require_choice(settings.get("pressure_velocity_coupling", "piso"),
                                  COUPLING_SCHEME_CODES, "pressure-velocity coupling"))]
    lines += ["", "/solve/set/discretization-scheme", "pressure",
              str(_require_choice(settings.get("pressure_scheme", "second_order"),
                                  PRESSURE_SCHEME_CODES, "pressure scheme"))]
    convection = [("mom", "momentum_scheme"), ("w-swirl", "swirl_scheme")]
    convection.extend((equation, f"{equation}_scheme") for equation in _model_equations(model))
    for tui_name, setting_name in convection:
        lines += [tui_name, str(_require_choice(settings.get(setting_name, "second_order_upwind"),
                                                 CONVECTION_SCHEME_CODES, setting_name))]
    return lines


def write_journal(path, blade, first, iteration, mesh_name="axisymmetric_mesh.msh",
                  fluent_iterations=200, fluent_settings=None):
    """Write a journal; only iteration one creates radial line surfaces."""
    path = Path(path)
    # Fluent surface IDs can contain gaps or change after a mesh replacement.
    # The line-surface names are stable and are accepted by the TUI anywhere
    # that a surface list is requested.
    facets = " ".join(f"line-{index:02d}" for index in range(1, len(blade.radius) + 1))
    case = "new_fluent_case_file.cas.h5" if first else "generated_coupling_case.cas.h5"
    lines = [f'/file/read-case "{case}"']
    if first:
        lines.append(f'/mesh/replace "{mesh_name}"')
        lines += [""] + first_iteration_setup(fluent_settings or {})
    if not first:
        lines.append(f'/file/read-data "coupled_solution_{iteration - 1}.dat.h5"')
    if first:
        lines += ["", "; Create radial surfaces once"]
        for index, (radius, width) in enumerate(zip(blade.radius, blade.dr), 1):
            inner = max(radius - width / 2, 0.045) if index == 1 else radius - width / 2
            outer = 0.45 if index == len(blade.radius) else radius + width / 2
            lines.append(f"/surface/line-surface line-{index:02d} 0 {inner:.10g} 0 {outer:.10g}")
        lines += ["", '/file/write-case "generated_coupling_case.cas.h5"']
    lines += ["", '/define/user-defined/execute-on-demand "read_ad_sources::libudf"',
              '/define/user-defined/execute-on-demand "display_ad_sources::libudf"']
    if first:
        lines.append("/solve/initialize/hyb-initialization yes")
    lines += [f"/solve/iterate {fluent_iterations}", "",
              f'/report/surface-integral facet-avg ({facets} ) axial-velocity yes "axial-report.txt"',
              f'/report/surface-integral facet-avg ({facets} ) swirl-velocity yes "tangential-report.txt"',
              f'/file/write-data "coupled_solution_{iteration}.dat.h5"', "/exit yes"]
    path.write_text("\n".join(lines) + "\n")


def run(executable, workdir, journal, processors=4):
    """Run Fluent in batch mode and return status plus combined output."""
    command = [executable, "2ddp", "-g", "-axisyswirl", f"-t{processors}", "-i", str(journal)]
    process = subprocess.Popen(command, cwd=workdir, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding="utf-8", errors="replace")
    lines = []
    for line in process.stdout:
        lines.append(line)
        print(line, end="", flush=True)
    return process.wait(), "".join(lines)
