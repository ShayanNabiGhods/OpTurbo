"""Build STEP profiles and their compound assembly without a duct."""

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
