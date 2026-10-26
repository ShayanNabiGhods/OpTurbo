"""Dependency-free checks for the open-turbine FreeCAD inputs."""

import math

from .parameters import OpenTurbineParameters


def validate_parameters(parameters: OpenTurbineParameters) -> None:
    """Reject dimensions that cannot form the open-turbine profile faces."""
    values = tuple(getattr(parameters, name) for name in parameters.__dataclass_fields__)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Open-turbine geometry dimensions must be finite.")
    positive = (
        parameters.domain_length, parameters.domain_height,
        parameters.resolution_length, parameters.resolution_inlet_radius,
        parameters.actuator_radial_span, parameters.actuator_thickness,
        parameters.hub_length, parameters.hub_radius,
    )
    if any(value <= 0 for value in positive):
        raise ValueError("Open-turbine lengths and radii must be positive.")
    if parameters.resolution_length <= parameters.resolution_inlet_radius:
        raise ValueError("The resolution region length must exceed its inlet radius.")
    if parameters.hub_length <= 2 * parameters.hub_radius:
        raise ValueError("Hub length must be greater than twice the hub radius.")
    rotor_outer_radius = parameters.hub_origin_r + parameters.hub_radius + parameters.actuator_radial_span
    domain_outer_radius = parameters.domain_origin_r + parameters.domain_height
    if parameters.hub_origin_r < parameters.domain_origin_r or rotor_outer_radius > domain_outer_radius:
        raise ValueError("The outer domain must contain the hub and actuator-disk radius.")
