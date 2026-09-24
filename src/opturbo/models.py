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
    spaceclaim: str = r"C:\Program Files\ANSYS Inc\v242\scdm\SpaceClaim.exe"
    workbench: str = r"C:\Program Files\ANSYS Inc\v242\Framework\bin\Win64\RunWB2.exe"
    fluent: str = r"C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe"
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


@dataclass
class MeshSettings:
    """Important ANSYS Meshing sizes in centimetres."""

    global_size_cm: float = 5.0
    curvature_angle_deg: float = 6.0
    resolution_size_cm: float = 0.5
    duct_size_cm: float = 0.3
    hub_size_cm: float = 0.5
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
    omega_rad_s: float = 133.33333333333331
    pitch_deg: float = 0.0
    stations: int = 36
    max_outer_iterations: int = 15
    fluent_iterations: int = 200
    tolerance: float = 1e-3
    relaxation: float = 0.3
    processors: int = 4
    keep_iteration_data: bool = True


@dataclass
class GaSettings:
    """Genetic-algorithm controls."""

    population_size: int = 12
    generations: int = 10
    elite_count: int = 2
    tournament_size: int = 3
    crossover_rate: float = 0.85
    mutation_rate: float = 0.20
    mutation_scale: float = 0.10
    random_seed: int = 42


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


def default_design_variables() -> list[VariableSpec]:
    """Return geometry and PARSEC variables displayed on the Design tab."""
    geometry = [
        VariableSpec("geometry.duct_angle_deg", "Duct angle of attack (deg)",
                     0.0, -8.0, 8.0, False),
        VariableSpec("geometry.duct_chord", "Duct chord length (mm)",
                     200.0, 160.0, 240.0, False),
    ]
    return geometry + default_parsec_variables()


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
    design_variables: list[VariableSpec] = field(default_factory=default_design_variables)

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration into JSON-compatible values."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Rebuild a configuration loaded from JSON."""
        geometry = GeometrySettings(**data.get("geometry", {}))
        raw_variables = data.get("design_variables", data.get("parsec_variables", []))
        variables = [VariableSpec(**item) for item in raw_variables]
        existing = {item.key for item in variables}
        for default in default_design_variables():
            if default.key not in existing:
                if default.key == "geometry.duct_angle_deg":
                    default.value = geometry.duct_angle_deg
                elif default.key == "geometry.duct_chord":
                    default.value = geometry.duct_chord
                variables.insert(0 if default.key.startswith("geometry.") else len(variables), default)
        return cls(
            project_name=data.get("project_name", "Untitled optimization"),
            save_dir=data.get("save_dir", ""),
            tools=ToolPaths(**data.get("tools", {})),
            geometry=geometry,
            mesh=MeshSettings(**data.get("mesh", {})),
            cfd=CfdSettings(**data.get("cfd", {})),
            ga=GaSettings(**data.get("ga", {})),
            design_variables=variables or default_design_variables(),
        )

    @property
    def save_path(self) -> Path | None:
        """Return the selected project path, if one has been chosen."""
        return Path(self.save_dir) if self.save_dir else None
