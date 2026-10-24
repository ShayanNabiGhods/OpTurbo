"""Meshing settings for the current axisymmetric workflow."""

from dataclasses import dataclass


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
