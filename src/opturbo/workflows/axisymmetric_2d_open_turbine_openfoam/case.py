"""Generate the OpenFOAM Foundation 14 case dictionaries for an open turbine."""

from __future__ import annotations

import math
from bisect import bisect_right
from pathlib import Path


def _number(value: float) -> str:
    """Format finite dictionary numbers without locale-dependent commas."""
    return f"{float(value):.12g}"


def _foam_file(object_name: str, location: str) -> str:
    return (
        "FoamFile\n{\n    format ascii;\n    class dictionary;\n"
        f'    location "{location}";\n    object {object_name};\n}}\n\n'
    )


def _field_file(object_name: str, location: str, field_class: str,
                dimensions: str, internal: str, boundary: str) -> str:
    return (
        "FoamFile\n{\n    format ascii;\n"
        f"    class {field_class};\n    location \"{location}\";\n"
        f"    object {object_name};\n}}\n\n"
        f"dimensions {dimensions};\n\ninternalField uniform {internal};\n\n"
        f"boundaryField\n{{\n{boundary}\n}}\n"
    )


def _patches(inlet: str, outlet: str, farfield: str, hub: str) -> str:
    return (
        f"    inlet\n    {{\n{inlet}\n    }}\n\n"
        f"    outlet\n    {{\n{outlet}\n    }}\n\n"
        f"    farfield\n    {{\n{farfield}\n    }}\n\n"
        f"    hub\n    {{\n{hub}\n    }}\n\n"
        "    axisCore { type symmetryPlane; }\n\n"
        "    wedge1 { type wedge; }\n    wedge2 { type wedge; }"
    )


def radial_zone_edges(blade, turbine) -> list[float]:
    """Build annular source-band edges around the BEM radial stations."""
    radii = blade.radius
    if len(radii) < 2 or any(right <= left for left, right in zip(radii, radii[1:])):
        raise ValueError("OpenFOAM actuator zones require at least two increasing BEM radii.")
    edges = [max(turbine.hub_radius, radii[0] - blade.dr[0] / 2)]
    edges.extend((left + right) / 2 for left, right in zip(radii, radii[1:]))
    edges.append(min(turbine.radius, radii[-1] + blade.dr[-1] / 2))
    if any(right <= left for left, right in zip(edges, edges[1:])):
        raise ValueError("OpenFOAM actuator-zone edges are not strictly increasing.")
    return edges


def axis_core_radius_m(geometry, mesh) -> float:
    """Clip the zero-area axis line from the single-cell wedge mesh."""
    return min(geometry.hub_radius * 0.5, mesh.global_size_cm * 2.5) / 1000


def _profile_radius(points: list[tuple[float, float]], x: float) -> float:
    """Linearly interpolate the FreeCAD-exported outer hub profile."""
    xs = [point[0] for point in points]
    if x <= xs[0] or x >= xs[-1]:
        return 0.0
    index = bisect_right(xs, x) - 1
    x0, r0 = points[index]
    x1, r1 = points[index + 1]
    fraction = (x - x0) / (x1 - x0)
    return r0 + fraction * (r1 - r0)


def write_block_mesh_dict(path: Path, geometry, mesh, settings,
                          profile_points: list[list[float]]) -> tuple[int, int]:
    """Write a structured wedge mesh fitted to FreeCAD's sampled hub profile."""
    domain_length = geometry.domain_length / 1000
    domain_height = geometry.domain_height / 1000
    x0 = geometry.domain_origin_x / 1000
    x1 = x0 + domain_length
    global_size = mesh.global_size_cm / 100
    resolution_size = mesh.resolution_size_cm / 100
    hub_size = mesh.hub_size_cm / 100
    profile = sorted((float(point[0]), float(point[1])) for point in profile_points)
    if (len(profile) < 3
            or any(not math.isfinite(value) for point in profile for value in point)
            or any(point[1] < 0 for point in profile)
            or any(b[0] <= a[0] for a, b in zip(profile, profile[1:]))):
        raise ValueError("FreeCAD hub profile must contain at least three increasing x/r samples.")
    if profile[0][0] < x0 or profile[-1][0] > x1:
        raise ValueError("FreeCAD hub profile lies outside the configured OpenFOAM domain.")
    inner_radius = axis_core_radius_m(geometry, mesh)
    hub_radius = geometry.hub_radius / 1000
    resolution_radius = geometry.resolution_inlet_radius / 1000
    wall_layer = min(5 * hub_size,
                     max(2 * hub_size, 0.25 * (resolution_radius - hub_radius)))
    resolution_radius = max(resolution_radius, hub_radius + wall_layer + resolution_size)
    resolution_radius = min(resolution_radius, domain_height - global_size)
    if not inner_radius < hub_radius < resolution_radius < domain_height:
        raise ValueError("OpenFOAM radial mesh regions do not fit inside the domain.")
    wall_cells = max(1, math.ceil(wall_layer / hub_size))
    resolution_cells = max(1, math.ceil(
        (resolution_radius - inner_radius - wall_layer) / resolution_size))
    farfield_cells = max(1, math.ceil((domain_height - resolution_radius) / global_size))
    radial_cells = wall_cells + resolution_cells + farfield_cells

    resolution_x0 = geometry.resolution_origin_x / 1000
    resolution_x1 = resolution_x0 + geometry.resolution_length / 1000
    breaks = [x0, x1, resolution_x0, resolution_x1, profile[0][0], profile[-1][0]]
    for (xa, ra), (xb, rb) in zip(profile, profile[1:]):
        if abs(ra - inner_radius) < 1e-10:
            breaks.append(xa)
        if (ra - inner_radius) * (rb - inner_radius) < 0:
            breaks.append(xa + (inner_radius - ra) * (xb - xa) / (rb - ra))
    breaks = sorted({round(value, 12) for value in breaks if x0 <= value <= x1})
    x_nodes = [breaks[0]]
    for left, right in zip(breaks, breaks[1:]):
        midpoint = (left + right) / 2
        if profile[0][0] <= midpoint <= profile[-1][0]:
            target = hub_size
        elif resolution_x0 <= midpoint <= resolution_x1:
            target = resolution_size
        else:
            target = global_size
        count = max(1, math.ceil((right - left) / target))
        x_nodes.extend(left + (right - left) * index / count
                       for index in range(1, count + 1))
    nx = len(x_nodes) - 1
    estimated_cells = nx * radial_cells
    if estimated_cells > settings.max_global_cells:
        raise ValueError(
            f"OpenFOAM blockMesh needs about {estimated_cells:,} cells, above the configured "
            f"limit of {settings.max_global_cells:,}. Increase mesh sizes or raise the cell limit."
        )

    radial_lines = []
    for x in x_nodes:
        wall_radius = max(inner_radius, _profile_radius(profile, x))
        radial_lines.append((wall_radius, wall_radius + wall_layer,
                             resolution_radius, domain_height))

    def vertex_id(x_index: int, radial_index: int, side: int) -> int:
        return x_index * 8 + radial_index * 2 + side

    half_angle = math.radians(settings.wedge_angle_deg / 2)
    vertices = []
    for x, radii in zip(x_nodes, radial_lines):
        for radius in radii:
            y = radius * math.cos(half_angle)
            z = radius * math.sin(half_angle)
            vertices.extend((
                f"    ({_number(x)} {_number(y)} -{_number(z)})",
                f"    ({_number(x)} {_number(y)} {_number(z)})",
            ))

    blocks = []
    inlet_faces, outlet_faces, farfield_faces = [], [], []
    hub_faces, axis_faces, wedge1_faces, wedge2_faces = [], [], [], []
    cells_per_band = (wall_cells, resolution_cells, farfield_cells)
    for index in range(nx):
        midpoint = (x_nodes[index] + x_nodes[index + 1]) / 2
        is_hub = _profile_radius(profile, midpoint) > inner_radius + 1e-10
        for band, radial_count in enumerate(cells_per_band):
            ids = (
                vertex_id(index, band, 0),
                vertex_id(index + 1, band, 0),
                vertex_id(index + 1, band + 1, 0),
                vertex_id(index, band + 1, 0),
                vertex_id(index, band, 1),
                vertex_id(index + 1, band, 1),
                vertex_id(index + 1, band + 1, 1),
                vertex_id(index, band + 1, 1),
            )
            blocks.append(
                f"    hex ({' '.join(map(str, ids))}) (1 {radial_count} 1) "
                "simpleGrading (1 1 1)"
            )
            if index == 0:
                inlet_faces.append((vertex_id(index, band, 0),
                                    vertex_id(index, band, 1),
                                    vertex_id(index, band + 1, 1),
                                    vertex_id(index, band + 1, 0)))
            if index == nx - 1:
                outlet_faces.append((vertex_id(index + 1, band, 0),
                                     vertex_id(index + 1, band + 1, 0),
                                     vertex_id(index + 1, band + 1, 1),
                                     vertex_id(index + 1, band, 1)))
            wedge1_faces.append((vertex_id(index, band, 0),
                                 vertex_id(index, band + 1, 0),
                                 vertex_id(index + 1, band + 1, 0),
                                 vertex_id(index + 1, band, 0)))
            wedge2_faces.append((vertex_id(index, band, 1),
                                 vertex_id(index + 1, band, 1),
                                 vertex_id(index + 1, band + 1, 1),
                                 vertex_id(index, band + 1, 1)))
        farfield_faces.append((vertex_id(index, 3, 0), vertex_id(index, 3, 1),
                               vertex_id(index + 1, 3, 1), vertex_id(index + 1, 3, 0)))
        inner_face = (vertex_id(index, 0, 0), vertex_id(index + 1, 0, 0),
                      vertex_id(index + 1, 0, 1), vertex_id(index, 0, 1))
        (hub_faces if is_hub else axis_faces).append(inner_face)

    def _patch(name: str, patch_type: str, faces: list[tuple[int, ...]]) -> str:
        face_text = "\n".join(f"        ({' '.join(map(str, face))})" for face in faces)
        return f"    {name}\n    {{\n        type {patch_type};\n        faces\n        (\n{face_text}\n        );\n    }}"

    boundary = "\n\n".join((
        _patch("inlet", "patch", inlet_faces),
        _patch("outlet", "patch", outlet_faces),
        _patch("farfield", "patch", farfield_faces),
        _patch("hub", "wall", hub_faces),
        _patch("axisCore", "symmetryPlane", axis_faces),
        _patch("wedge1", "wedge", wedge1_faces),
        _patch("wedge2", "wedge", wedge2_faces),
    ))
    contents = (
        _foam_file("blockMeshDict", "system")
        + "units [m];\n\nvertices\n(\n" + "\n".join(vertices) + "\n);\n\n"
        + "blocks\n(\n" + "\n".join(blocks) + "\n);\n\nedges ();\n\nboundary\n(\n"
        + boundary + "\n);\n"
    )
    path.write_text(contents, encoding="utf-8")
    return nx, radial_cells


def write_topo_set_dict(path: Path, edges: list[float], geometry, cfd) -> None:
    """Create one cellZone for each BEM station's actuator-disk annulus."""
    half_width = geometry.actuator_thickness / 2000
    x0 = geometry.actuator_origin_x / 1000 - half_width
    x1 = geometry.actuator_origin_x / 1000 + half_width
    actions = []
    for index, (inner, outer) in enumerate(zip(edges, edges[1:])):
        name = f"rotorBand{index:03d}"
        actions.extend((
            f"""    {{
        name {name};
        type cellSet;
        action new;
        source cylinderToCell;
        sourceInfo {{ p1 ({_number(x0)} 0 0); p2 ({_number(x1)} 0 0); radius {_number(outer)}; }}
    }}""",
            f"""    {{
        name {name};
        type cellSet;
        action delete;
        source cylinderToCell;
        sourceInfo {{ p1 ({_number(x0)} 0 0); p2 ({_number(x1)} 0 0); radius {_number(inner)}; }}
    }}""",
            f"""    {{
        name {name};
        type cellZoneSet;
        action new;
        source setToCellZone;
        sourceInfo {{ set {name}; }}
    }}""",
        ))
    content = (
        _foam_file("topoSetDict", "system") + "actions\n(\n"
        + "\n".join(actions) + "\n);\n"
    )
    path.write_text(content, encoding="utf-8")


def write_case_fields(case_dir: Path, geometry, cfd, openfoam, model: str) -> None:
    """Write the Foundation 14 steady incompressible RANS initial fields."""
    initial = case_dir / "0"
    initial.mkdir(parents=True, exist_ok=True)
    speed = cfd.flow_speed_m_s
    intensity = openfoam.turbulence_intensity
    k_value = 1.5 * (speed * intensity) ** 2
    length_scale = 0.07 * 2 * cfd.rotor_radius_m
    epsilon = 0.09 ** 0.75 * k_value ** 1.5 / length_scale
    omega = math.sqrt(k_value) / (0.09 ** 0.25 * length_scale)
    nu = cfd.viscosity_pa_s / cfd.density_kg_m3
    nu_tilda = 3 * nu
    u_patches = _patches(
        f"        type fixedValue;\n        value uniform ({_number(speed)} 0 0);",
        "        type pressureInletOutletVelocity;\n        value uniform (0 0 0);",
        "        type slip;",
        "        type noSlip;",
    )
    p_patches = _patches(
        "        type zeroGradient;",
        "        type fixedValue;\n        value uniform 0;",
        "        type zeroGradient;",
        "        type zeroGradient;",
    )
    nut_wall = "nutUSpaldingWallFunction" if model == "spalart_allmaras" else "nutkWallFunction"
    nut_patches = _patches(
        "        type calculated;\n        value uniform 0;",
        "        type calculated;\n        value uniform 0;",
        "        type calculated;\n        value uniform 0;",
        f"        type {nut_wall};\n        value uniform 0;",
    )
    (initial / "U").write_text(_field_file(
        "U", "0", "volVectorField", "[0 1 -1 0 0 0 0]", "(0 0 0)", u_patches), encoding="utf-8")
    (initial / "p").write_text(_field_file(
        "p", "0", "volScalarField", "[0 2 -2 0 0 0 0]", "0", p_patches), encoding="utf-8")
    (initial / "nut").write_text(_field_file(
        "nut", "0", "volScalarField", "[0 2 -1 0 0 0 0]", "0", nut_patches), encoding="utf-8")
    common = {
        "inlet": "        type fixedValue;\n        value uniform {value};",
        "outlet": "        type zeroGradient;",
        "farfield": "        type zeroGradient;",
        "hub": "        type {wall};\n        value uniform {value};",
    }
    if model == "k_epsilon":
        for field, value, wall in (("k", k_value, "kqRWallFunction"),
                                   ("epsilon", epsilon, "epsilonWallFunction")):
            patches = _patches(
                common["inlet"].format(value=_number(value)), common["outlet"],
                common["farfield"], common["hub"].format(wall=wall, value=_number(value)),
            )
            dimensions = "[0 2 -2 0 0 0 0]" if field == "k" else "[0 2 -3 0 0 0 0]"
            (initial / field).write_text(_field_file(
                field, "0", "volScalarField", dimensions, _number(value), patches), encoding="utf-8")
    elif model == "k_omega":
        for field, value, wall, dimensions in (
            ("k", k_value, "kqRWallFunction", "[0 2 -2 0 0 0 0]"),
            ("omega", omega, "omegaWallFunction", "[0 0 -1 0 0 0 0]"),
        ):
            patches = _patches(
                common["inlet"].format(value=_number(value)), common["outlet"],
                common["farfield"], common["hub"].format(wall=wall, value=_number(value)),
            )
            (initial / field).write_text(_field_file(
                field, "0", "volScalarField", dimensions, _number(value), patches), encoding="utf-8")
    else:
        patches = _patches(
            common["inlet"].format(value=_number(nu_tilda)), common["outlet"],
            common["farfield"], "        type fixedValue;\n        value uniform 0;",
        )
        (initial / "nuTilda").write_text(_field_file(
            "nuTilda", "0", "volScalarField", "[0 2 -1 0 0 0 0]",
            _number(nu_tilda), patches), encoding="utf-8")
    constant = case_dir / "constant"
    (constant / "physicalProperties").write_text(
        _foam_file("physicalProperties", "constant")
        + f"viscosityModel constant;\n\nnu {_number(nu)};\n",
        encoding="utf-8",
    )
    model_name = {"k_epsilon": "kEpsilon", "k_omega": "kOmegaSST",
                  "spalart_allmaras": "SpalartAllmaras"}[model]
    (constant / "momentumTransport").write_text(
        _foam_file("momentumTransport", "constant")
        + f"simulationType RAS;\n\nRAS\n{{\n    model {model_name};\n    turbulence on;\n}}\n",
        encoding="utf-8",
    )


def write_system_dictionaries(case_dir: Path, cfd, openfoam, model: str,
                              blade, actuator_x_m: float,
                              end_time: int | None = None) -> None:
    """Write solver, sampling, and steady run controls for OpenFOAM 14."""
    system = case_dir / "system"
    system.mkdir(parents=True, exist_ok=True)
    write_schemes = {
        "k_epsilon": "    div(phi,k) Gauss upwind;\n    div(phi,epsilon) Gauss upwind;",
        "k_omega": "    div(phi,k) Gauss upwind;\n    div(phi,omega) Gauss upwind;",
        "spalart_allmaras": "    div(phi,nuTilda) bounded Gauss linearUpwind grad(nuTilda);",
    }[model]
    (system / "fvSchemes").write_text(
        _foam_file("fvSchemes", "system")
        + """ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
""" + write_schemes + "\n    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n"
        "laplacianSchemes { default Gauss linear corrected; }\n"
        "interpolationSchemes { default linear; }\n"
        "snGradSchemes { default corrected; }\n"
        "wallDist { method meshWave; }\n",
        encoding="utf-8",
    )
    tolerance = _number(openfoam.solver_tolerance)
    relaxation = _number(openfoam.solver_relaxation)
    (system / "fvSolution").write_text(
        _foam_file("fvSolution", "system")
        + f"""solvers
{{
    p
    {{ solver GAMG; smoother GaussSeidel; tolerance {tolerance}; relTol 0.05; }}
    "(U|k|epsilon|omega|nuTilda)"
    {{ solver smoothSolver; smoother symGaussSeidel; tolerance {tolerance}; relTol 0.1; }}
}}
SIMPLE {{ nNonOrthogonalCorrectors 0; consistent yes; }}
relaxationFactors
{{
    fields {{ p 0.3; }}
    equations {{ U {relaxation}; "(k|epsilon|omega|nuTilda)" {relaxation}; }}
}}
""",
        encoding="utf-8",
    )
    locations = "\n".join(
        f"        ({_number(actuator_x_m)} {_number(radius)} 0)"
        for radius in blade.radius
    )
    functions = f"""functions
{{
actuatorDisk
{{
    libs ("libsampling.so");
    type probes;
    writeControl writeTime;
    writeInterval 1;
    fields (U);
    probeLocations
    (
{locations}
    );
}}
}}
"""
    end = end_time if end_time is not None else max(1, cfd.fluent_iterations)
    purge = 0 if cfd.keep_iteration_data else 2
    (system / "controlDict").write_text(
        _foam_file("controlDict", "system")
        + f"""application simpleFoam;
startFrom latestTime;
stopAt endTime;
endTime {end};
deltaT 1;
writeControl timeStep;
writeInterval {max(1, cfd.fluent_iterations)};
purgeWrite {purge};
writeFormat ascii;
writePrecision 10;
writeCompression off;
timeFormat general;
timePrecision 8;
runTimeModifiable true;
{functions}
""",
        encoding="utf-8",
    )


def write_fv_models(path: Path, axial: list[float], tangential: list[float],
                    density: float) -> None:
    """Write one volumetric OpenFOAM momentum source per radial BEM band."""
    if len(axial) != len(tangential):
        raise ValueError("OpenFOAM axial and tangential source arrays must have equal lengths.")
    entries = []
    for index, (sx, st) in enumerate(zip(axial, tangential)):
        if not math.isfinite(sx) or not math.isfinite(st):
            raise ValueError("OpenFOAM actuator sources must be finite.")
        entries.append(
            f"""rotorBand{index:03d}
{{
    type semiImplicitSource;
    cellZone rotorBand{index:03d};
    volumeMode specific;
    sources
    {{
        U
        {{
            explicit ({_number(sx / density)} 0 {_number(st / density)});
            implicit 0;
        }}
    }}
}}"""
        )
    Path(path).write_text(
        _foam_file("fvModels", "constant") + "\n\n".join(entries) + "\n",
        encoding="utf-8",
    )
