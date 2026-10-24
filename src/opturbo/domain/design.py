"""Duct geometry settings and design-variable defaults."""

from dataclasses import dataclass


@dataclass
class VariableSpec:
    """Describe one duct design variable and its optimization bounds."""

    key: str
    label: str
    value: float
    minimum: float
    maximum: float
    optimize: bool = True

    def clamp(self, candidate: float) -> float:
        """Return a value kept inside this variable's bounds."""
        return min(self.maximum, max(self.minimum, candidate))

@dataclass
class GeometrySettings:
    """Domain, rotor, hub, and duct placement settings in millimetres."""

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

def default_parsec_variables() -> list[VariableSpec]:
    """Return the original duct PARSEC values with conservative bounds."""
    rows = (
        ("upper.leading_edge_radius", "Upper leading-edge radius", 0.0162187, 0.003, 0.05),
        ("upper.crest_location", "Upper crest location", 0.376723, 0.15, 0.65),
        ("upper.crest_height", "Upper crest height", 0.101977, 0.04, 0.20),
        ("upper.crest_curvature", "Upper crest curvature", -1.11136, -3.0, -0.1),
        ("upper.trailing_edge_height", "Upper trailing-edge height", 0.0, -0.03, 0.03),
        ("upper.trailing_edge_slope_deg", "Upper trailing-edge slope", -12.9184, -30.0, 5.0),
        ("lower.leading_edge_radius", "Lower leading-edge radius", 0.00748922, 0.002, 0.04),
        ("lower.crest_location", "Lower crest location", 0.36, 0.15, 0.65),
        ("lower.crest_height", "Lower crest height", -0.11, -0.22, -0.03),
        ("lower.crest_curvature", "Lower crest curvature", 1.64354, 0.1, 3.5),
        ("lower.trailing_edge_height", "Lower trailing-edge height", 0.0, -0.03, 0.03),
        ("lower.trailing_edge_slope_deg", "Lower trailing-edge slope", 0.148211, -10.0, 20.0),
    )
    return [VariableSpec(*row) for row in rows]

def default_airfoil_variables() -> list[VariableSpec]:
    """Return variables for the original, full-airfoil duct."""
    geometry = [
        VariableSpec("geometry.duct_angle_deg", "Duct angle of attack (deg)",
                     0.0, -8.0, 8.0, False),
        VariableSpec("geometry.duct_chord", "Duct chord length (mm)",
                     200.0, 160.0, 240.0, False),
    ]
    return geometry + default_parsec_variables()

def default_flanged_variables() -> list[VariableSpec]:
    """Return variables for the five-term lower contour with a flange."""
    geometry = [
        VariableSpec("geometry.duct_chord", "Duct chord length (mm)",
                     90.0, 60.0, 240.0, False),
        VariableSpec("geometry.duct_thickness", "Duct wall thickness (mm)",
                     1.0, 0.5, 10.0, False),
        VariableSpec("geometry.duct_flange_length", "Flange length (mm)",
                     90.0, 60.0, 120.0, False),
        VariableSpec("geometry.duct_flange_angle_deg", "Flange angle (deg)",
                     85.0, 80.0, 90.0, True),
    ]
    curve = [
        VariableSpec("lower.crest_location", "Crest location", 0.3, 0.25, 0.35),
        VariableSpec("lower.crest_height", "Crest height", -0.15, -0.175, -0.125),
        VariableSpec("lower.crest_curvature", "Crest curvature", 2.0, 0.5, 3.0),
        VariableSpec("lower.trailing_edge_height", "Trailing-edge height", 0.1, 0.0, 0.3),
        VariableSpec("lower.trailing_edge_slope_deg", "Trailing-edge slope (deg)", 0.0, -20.0, 20.0),
    ]
    return geometry + curve

def default_design_variables(design_type: str = "airfoil") -> list[VariableSpec]:
    """Return only the optimization choices applicable to the duct family."""
    if design_type == "flanged":
        return default_flanged_variables()
    if design_type != "airfoil":
        raise ValueError(f"Unknown duct design type: {design_type}")
    return default_airfoil_variables()
