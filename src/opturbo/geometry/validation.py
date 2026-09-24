"""Dimension checks that do not require FreeCAD."""

from .config import DesignParameters


def validate_parameters(parameters: DesignParameters) -> None:
    """Reject dimensions that would produce an invalid profile."""
    positive = (
        parameters.domain_length, parameters.domain_height,
        parameters.resolution_length,
        parameters.resolution_inlet_radius, parameters.actuator_radial_span,
        parameters.actuator_thickness, parameters.hub_length,
        parameters.hub_radius, parameters.duct_chord, parameters.duct_points,
    )
    if any(value <= 0 for value in positive):
        raise ValueError("All dimensions must be positive.")
    if parameters.hub_length <= 2 * parameters.hub_radius:
        raise ValueError("hub_length must be greater than two hub radii.")


def actuator_outer_radius(parameters: DesignParameters) -> float:
    """Return the actuator outer radius from hub radius plus radial span."""
    return parameters.hub_radius + parameters.actuator_radial_span
