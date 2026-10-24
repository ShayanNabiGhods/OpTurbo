"""Compatibility imports for the axisymmetric design preview geometry."""

from .workflows.axisymmetric_2d.geometry.preview import (
    actuator_outline,
    hub_outline,
    outer_domain_outline,
    resolution_outline,
)

__all__ = [
    "actuator_outline", "hub_outline", "outer_domain_outline",
    "resolution_outline",
]
