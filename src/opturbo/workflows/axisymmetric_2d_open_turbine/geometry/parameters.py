"""Only the dimensions used by the open-turbine CAD assembly."""

from dataclasses import dataclass


OUTPUT_NAMES = {
    "domain": "outer_domain.step",
    "resolution": "resolution_section.step",
    "actuator": "actuator_disk.step",
    "hub": "hub.step",
    "assembly": "open_turbine_assembly.step",
}


@dataclass(frozen=True)
class OpenTurbineParameters:
    """Store domain, resolution, actuator-disk and hub dimensions in mm."""

    domain_length: float = 9000.0
    domain_height: float = 6750.0
    domain_origin_x: float = -2250.0
    domain_origin_r: float = 0.0
    resolution_length: float = 2700.0
    resolution_inlet_radius: float = 900.0
    resolution_origin_x: float = -900.0
    resolution_origin_r: float = 0.0
    actuator_radial_span: float = 405.0
    actuator_thickness: float = 5.0
    actuator_origin_x: float = 2.5
    hub_length: float = 800.0
    hub_radius: float = 45.0
    hub_origin_x: float = 335.0
    hub_origin_r: float = 0.0
