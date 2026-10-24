"""Compatibility imports for axisymmetric design-file reading."""

from .workflows.axisymmetric_2d.geometry.design_import import (
    DesignSnapshot,
    read_design_snapshot,
)

__all__ = ["DesignSnapshot", "read_design_snapshot"]
