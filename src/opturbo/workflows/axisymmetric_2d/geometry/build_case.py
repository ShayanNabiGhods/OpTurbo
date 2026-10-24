"""Build and export all DAWT profiles."""

from pathlib import Path

import Part

from .config import DesignParameters, OUTPUT_NAMES
from .freecad_helpers import add_shape, export_shape, make_document
from .duct import duct
from .profiles import actuator_disk, hub, rectangle, resolution_section
from .validation import validate_parameters


def build_case(parameters: DesignParameters, output_dir: Path) -> list[Path]:
    """Create five STEP profiles and one overlapping compound assembly."""
    validate_parameters(parameters)
    shapes = {
        "domain": rectangle(parameters),
        "resolution": resolution_section(parameters),
        "actuator": actuator_disk(parameters),
        "hub": hub(parameters),
        "duct": duct(parameters),
    }
    document = make_document()
    for name, shape in shapes.items():
        add_shape(document, name, shape)
    assembly = Part.makeCompound(list(shapes.values()))
    add_shape(document, "profile_assembly", assembly)
    document.recompute()
    names = ("domain", "resolution", "actuator", "hub", "duct")
    paths = [export_shape(shapes[name], output_dir / OUTPUT_NAMES[name])
             for name in names]
    paths.append(export_shape(assembly, output_dir / OUTPUT_NAMES["assembly"]))
    return paths
