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
    actuator_origin_x: float = 2.5
    hub_length: float = 800.0
    hub_radius: float = 45.0
    hub_origin_x: float = 335.0
    hub_origin_r: float = 0.0
    duct_origin_x: float = -24.5
    duct_origin_r: float = 469.5
    design_type: str = "flanged"
    duct_chord: float = 90.0
    duct_thickness: float = 1.0
    duct_angle_deg: float = 0.0
    duct_flange_length: float = 90.0
    duct_flange_angle_deg: float = 85.0
    duct_reverse: bool = False
    duct_points: int = 180
    parsec: dict = field(default_factory=lambda: {
        "upper": {"leading_edge_radius": 0.0162187, "crest_location": 0.376723,
                  "crest_height": 0.101977, "crest_curvature": -1.11136,
                  "trailing_edge_height": 0.0, "trailing_edge_slope_deg": -12.9184},
        "lower": {"leading_edge_radius": 0.00748922, "crest_location": 0.360,
                  "crest_height": -0.11, "crest_curvature": 1.64354,
                  "trailing_edge_height": 0.0, "trailing_edge_slope_deg": 0.148211},
    })
    flanged_curve: dict = field(default_factory=lambda: {
        "crest_location": 0.3, "crest_height": -0.15,
        "crest_curvature": 2.0, "trailing_edge_height": 0.1,
        "trailing_edge_slope_deg": 0.0,
    })


OUTPUT_NAMES = {
    "domain": "outer_domain.step",
    "resolution": "resolution_section.step",
    "actuator": "actuator_disk.step",
    "hub": "hub.step",
    "duct": "duct.step",
    "assembly": "profile_assembly.step",
}
