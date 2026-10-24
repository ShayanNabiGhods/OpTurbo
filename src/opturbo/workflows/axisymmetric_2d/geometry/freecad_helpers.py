"""Small wrappers around the FreeCAD and Part APIs."""

from pathlib import Path

import FreeCAD as App


def checked(shape, name: str):
    """Return a shape, raising a useful error for invalid geometry."""
    if shape.isNull():
        raise RuntimeError(f"{name} is null.")
    if not shape.isValid():
        raise RuntimeError(f"{name} is invalid.")
    return shape


def make_document():
    """Create the temporary FreeCAD document used for export."""
    return App.newDocument("dawt_profiles")


def add_shape(document, name: str, shape):
    """Add a shape to a document so it can be inspected in FreeCAD."""
    feature = document.addObject("Part::Feature", name)
    feature.Label = name
    feature.Shape = shape
    return feature


def export_shape(shape, path: Path) -> Path:
    """Export one shape or compound to a STEP file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shape.exportStep(str(path))
    return path
