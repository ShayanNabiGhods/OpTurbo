"""User-editable dimensions and output names."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DesignParameters:
    """Store profile dimensions and the independent origin of each shape."""

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
    actuator_origin_x: float = -2.5
    hub_length: float = 800.0
    hub_radius: float = 45.0
    hub_origin_x: float = 335.0
    hub_origin_r: float = 0.0
    duct_origin_x: float = -72.0
    duct_origin_r: float = 475.0
    duct_chord: float = 200.0
    duct_angle_deg: float = 0.0
    duct_reverse: bool = True
    duct_points: int = 180
    parsec: dict = field(default_factory=lambda: {
        "upper": {"leading_edge_radius": 0.0162187, "crest_location": 0.376723,
                  "crest_height": 0.101977, "crest_curvature": -1.11136,
                  "trailing_edge_height": 0.0, "trailing_edge_slope_deg": -12.9184},
        "lower": {"leading_edge_radius": 0.00748922, "crest_location": 0.360,
                  "crest_height": -0.11, "crest_curvature": 1.64354,
                  "trailing_edge_height": 0.0, "trailing_edge_slope_deg": 0.148211},
    })


OUTPUT_NAMES = {
    "domain": "outer_domain.step",
    "resolution": "resolution_section.step",
    "actuator": "actuator_disk.step",
    "hub": "hub.step",
    "duct": "duct.step",
    "assembly": "profile_assembly.step",
}
