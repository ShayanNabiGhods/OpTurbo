"""Fluent journal generation and optional persistent-state execution."""

import subprocess
from pathlib import Path


def write_journal(path, blade, first, iteration, mesh_name="axisymmetric_mesh.msh", fluent_iterations=200):
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
