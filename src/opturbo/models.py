"""Small data models shared by the GUI, optimizer, and pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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
class ToolPaths:
    """External executable paths and the immutable SpaceClaim handoff path."""

    freecad: str = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"
    spaceclaim: str = r"C:\Program Files\ANSYS Inc\v241\scdm\SpaceClaim.exe"
    workbench: str = r"C:\Program Files\ANSYS Inc\v241\Framework\bin\Win64\RunWB2.exe"
    fluent: str = r"C:\Program Files\ANSYS Inc\v241\fluent\ntbin\win64\fluent.exe"
    handoff_dir: str = r"C:\OpTurbo\Temp Files"


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


@dataclass
class MeshSettings:
    """Important ANSYS Meshing sizes in centimetres."""

    global_size_cm: float = 3.0
    growth_rate: float = 1.1
    cpu_cores: int | None = None
    method: str = "Quad"
    curvature_angle_deg: float = 5.0
    resolution_size_cm: float = 1.0
    duct_size_cm: float = 0.3
    hub_size_cm: float = 0.3
    inflation_enabled: bool = True
    inflation_layers: int = 5
    inflation_max_thickness_cm: float = 0.2


@dataclass
class CfdSettings:
    """Important Fluent/BEM coupling controls."""

    flow_speed_m_s: float = 10.0
    density_kg_m3: float = 1.187
    viscosity_pa_s: float = 1.81e-5
    rotor_radius_m: float = 0.45
    hub_radius_m: float = 0.045
    blades: int = 3
    omega_rad_s: float = 133.33
    pitch_deg: float = 0.0
    tip_loss_model: str = "bontempo2025"
    bontempo_g_a: float = -0.229
    bontempo_g_b: float = 22.0116
    bontempo_g_c: float = 0.4427
    stations: int = 36
    max_outer_iterations: int = 15
    fluent_iterations: int = 300
    tolerance: float = 1e-3
    relaxation: float = 0.7
    processors: int = 12
    keep_iteration_data: bool = True
    viscous_model: str = "k_epsilon"
    residual_continuity: float = 1e-5
    residual_x_velocity: float = 1e-5
    residual_y_velocity: float = 1e-5
    residual_swirl: float = 1e-5
    residual_k: float = 1e-5
    residual_epsilon: float = 1e-5
    residual_omega: float = 1e-4
    residual_nut: float = 1e-4
    pressure_scheme: str = "presto"
    source_initialization: str = "conservative"
    previous_source_weight: float = 1.0
    momentum_scheme: str = "quick"
    swirl_scheme: str = "quick"
    k_scheme: str = "quick"
    epsilon_scheme: str = "quick"
    omega_scheme: str = "second_order_upwind"
    nut_scheme: str = "second_order_upwind"
    pressure_velocity_coupling: str = "coupled"


@dataclass
class GaSettings:
    """Genetic-algorithm controls."""

    population_size: int = 8
    generations: int = 10
    elite_count: int = 2
    tournament_size: int = 3
    crossover_rate: float = 0.85
    mutation_rate: float = 0.20
    mutation_scale: float = 0.10
    random_seed: int = 42
    overlap_preparation: bool = False
    objective: str = "cp"


@dataclass
class AccessibilitySettings:
    """Store visual preferences that make the desktop interface easier to use."""

    theme: str = "light"
    text_scale: int = 100
    high_contrast: bool = False
    accent_color: str = "#2f6fed"
    candidate_marker_size: int = 5
    outer_marker_size: int = 5
    table_row_spacing: int = 0


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


@dataclass
class ProjectConfig:
    """Complete serializable application configuration."""

    project_name: str = "Untitled optimization"
    save_dir: str = ""
    tools: ToolPaths = field(default_factory=ToolPaths)
    geometry: GeometrySettings = field(default_factory=GeometrySettings)
    mesh: MeshSettings = field(default_factory=MeshSettings)
    cfd: CfdSettings = field(default_factory=CfdSettings)
    ga: GaSettings = field(default_factory=GaSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    design_variables: list[VariableSpec] = field(
        default_factory=lambda: default_design_variables("flanged"))

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration into JSON-compatible values."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Rebuild a configuration loaded from JSON."""
        geometry_data = dict(data.get("geometry", {}))
        # Saved projects created before duct-family selection were airfoil-based.
        if "design_type" not in geometry_data:
            geometry_data["design_type"] = "airfoil"
        geometry = GeometrySettings(**geometry_data)
        raw_variables = data.get("design_variables", data.get("parsec_variables", []))
        variables = [VariableSpec(**item) for item in raw_variables]
        defaults = default_design_variables(geometry.design_type)
        allowed = {item.key for item in defaults}
        variables = [item for item in variables if item.key in allowed]
        existing = {item.key for item in variables}
        for default in defaults:
            if default.key not in existing:
                if default.key == "geometry.duct_angle_deg":
                    default.value = geometry.duct_angle_deg
                elif default.key == "geometry.duct_chord" and "duct_chord" in geometry_data:
                    default.value = geometry.duct_chord
                elif default.key == "geometry.duct_thickness" and "duct_thickness" in geometry_data:
                    default.value = geometry.duct_thickness
                elif default.key == "geometry.duct_flange_length" and "duct_flange_length" in geometry_data:
                    default.value = geometry.duct_flange_length
                elif default.key == "geometry.duct_flange_angle_deg" and "duct_flange_angle_deg" in geometry_data:
                    default.value = geometry.duct_flange_angle_deg
                variables.insert(0 if default.key.startswith("geometry.") else len(variables), default)
        cfd_data = dict(data.get("cfd", {}))
        # Older projects may contain this retired setting; never forward it.
        cfd_data.pop("gradient_scheme", None)
        return cls(
            project_name=data.get("project_name", "Untitled optimization"),
            save_dir=data.get("save_dir", ""),
            tools=ToolPaths(**data.get("tools", {})),
            geometry=geometry,
            mesh=MeshSettings(**data.get("mesh", {})),
            cfd=CfdSettings(**cfd_data),
            ga=GaSettings(**data.get("ga", {})),
            accessibility=AccessibilitySettings(**data.get("accessibility", {})),
            design_variables=variables or defaults,
        )

    @property
    def save_path(self) -> Path | None:
        """Return the selected project path, if one has been chosen."""
        return Path(self.save_dir) if self.save_dir else None
