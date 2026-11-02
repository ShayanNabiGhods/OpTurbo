"""Run-time controls specific to the OpenFOAM open-turbine workflow."""

from dataclasses import dataclass


@dataclass
class OpenFoamSettings:
    """OpenFOAM mesh limits, solver controls, and inlet turbulence inputs."""

    max_global_cells: int = 2_000_000
    solver_tolerance: float = 1e-6
    solver_relaxation: float = 0.7
    turbulence_intensity: float = 0.05
    wedge_angle_deg: float = 5.0
