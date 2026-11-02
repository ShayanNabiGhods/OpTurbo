"""Build STEP profiles and their compound assembly without a duct."""

import json
from pathlib import Path

import Part

from ...axisymmetric_2d.geometry.freecad_helpers import add_shape, export_shape, make_document
from ...axisymmetric_2d.geometry.profiles import actuator_disk, hub, rectangle, resolution_section
from .parameters import OUTPUT_NAMES, OpenTurbineParameters
from .validation import validate_parameters


def build_open_case(parameters: OpenTurbineParameters, output_dir: Path) -> list[Path]:
    """Export domain, resolution region, disk, hub, and a duct-free assembly."""
    validate_parameters(parameters)
    shapes = {
        "domain": rectangle(parameters),
        "resolution": resolution_section(parameters),
        "actuator": actuator_disk(parameters),
        "hub": hub(parameters),
    }
    document = make_document()
    for name, shape in shapes.items():
        add_shape(document, name, shape)
    assembly = Part.makeCompound(list(shapes.values()))
    add_shape(document, "open_turbine_assembly", assembly)
    document.recompute()
    paths = [export_shape(shape, Path(output_dir) / OUTPUT_NAMES[name])
             for name, shape in shapes.items()]
    paths.append(export_shape(assembly, Path(output_dir) / OUTPUT_NAMES["assembly"]))
    return paths


def export_openfoam_hub_surface(parameters: OpenTurbineParameters, path: Path) -> Path:
    """Revolve the meridional FreeCAD hub profile and write an SI-unit STL."""
    import MeshPart
    import FreeCAD as App

    validate_parameters(parameters)
    profile = hub(parameters)
    solid = profile.revolve(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 360.0)
    if solid.isNull() or not solid.isValid() or not solid.isClosed():
        raise RuntimeError("FreeCAD could not create a closed revolved hub for OpenFOAM.")
    surface = MeshPart.meshFromShape(
        Shape=solid, LinearDeflection=0.5, AngularDeflection=0.15, Relative=False,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # ASCII STL is readable by OpenFOAM and avoids a second, version-sensitive
    # conversion step. FreeCAD dimensions are mm; OpenFOAM uses metres.
    with path.open("w", encoding="ascii", newline="\n") as handle:
        handle.write("solid openfoam_hub\n")
        for facet in surface.Facets:
            normal = facet.Normal
            handle.write(f" facet normal {normal.x:.9g} {normal.y:.9g} {normal.z:.9g}\n")
            handle.write("  outer loop\n")
            for point in facet.Points:
                # MeshPart returns triangle vertices as 3-tuples in FreeCAD 1.1.
                handle.write(
                    f"   vertex {point[0] / 1000:.12g} {point[1] / 1000:.12g} {point[2] / 1000:.12g}\n"
                )
            handle.write("  endloop\n endfacet\n")
        handle.write("endsolid openfoam_hub\n")
    if not surface.Facets:
        raise RuntimeError("FreeCAD created an empty triangulated hub surface.")
    # Carry the exact CAD meridional profile into the structured OpenFOAM mesh.
    # Omit the line on the rotation axis; it bounds the solid in CAD but not the
    # outer hub wall used by the fluid mesh.
    points = []
    for edge in profile.Edges:
        vertices = edge.Vertexes
        if vertices and all(abs(vertex.Point.y - parameters.hub_origin_r) < 1e-7
                            for vertex in vertices):
            continue
        for point in edge.discretize(Deflection=0.25):
            x, radius = ((point.x, point.y) if hasattr(point, "x")
                         else (point[0], point[1]))
            points.append((round(x / 1000, 12),
                           round((radius - parameters.hub_origin_r) / 1000, 12)))
    profile_by_x = {}
    for x, radius in points:
        profile_by_x[x] = max(radius, profile_by_x.get(x, 0.0))
    profile_points = [[x, profile_by_x[x]] for x in sorted(profile_by_x)]
    if len(profile_points) < 3:
        raise RuntimeError("FreeCAD could not sample the outer hub profile for blockMesh.")
    profile_path = path.with_name("openfoam_hub_profile.json")
    profile_path.write_text(json.dumps({
        "units": "m", "points": profile_points,
    }, indent=2), encoding="utf-8")
    return path
