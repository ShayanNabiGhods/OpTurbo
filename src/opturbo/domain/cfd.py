"""Fluent and BEM settings for the current axisymmetric workflow."""

from dataclasses import dataclass


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
