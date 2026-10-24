"""Validation rules for current OpTurbo project inputs."""

import math

from .choices import CFD_CHOICE_VALUES
from .project import ProjectConfig


def validate_project_settings(config: ProjectConfig) -> None:
    """Raise ``ValueError`` for invalid engineering settings before tool use.

    Length fields retain their model units (millimetres for geometry and
    centimetres for mesh sizes); flow inputs use SI units. This function does
    not mutate the configuration or start external processes.
    """
    for section_name, settings in (
        ("geometry", config.geometry),
        ("mesh", config.mesh),
        ("cfd", config.cfd),
        ("ga", config.ga),
    ):
        for name, value in vars(settings).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(value):
                    raise ValueError(f"{section_name}.{name} must be a finite number.")

    for variable in config.design_variables:
        values = (variable.value, variable.minimum, variable.maximum)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"{variable.label} values and bounds must be finite.")
        if variable.minimum >= variable.maximum:
            raise ValueError(f"{variable.label}: minimum must be less than maximum.")
        if not variable.minimum <= variable.value <= variable.maximum:
            raise ValueError(f"{variable.label}: value must be inside its bounds.")

    if config.cfd.tip_loss_model not in {"prandtl", "bontempo2025"}:
        raise ValueError("Choose a valid tip-loss correction model.")
    if not all(math.isfinite(value) for value in (
            config.cfd.bontempo_g_a, config.cfd.bontempo_g_b, config.cfd.bontempo_g_c)):
        raise ValueError("Bontempo g coefficients must be finite numbers.")
    if config.geometry.design_type not in {"airfoil", "flanged"}:
        raise ValueError("Choose either the airfoil or flanged duct design.")
    if (config.geometry.duct_chord <= 0 or config.geometry.duct_thickness <= 0 or
            config.geometry.domain_length <= 0 or config.geometry.domain_height <= 0):
        raise ValueError("Geometry lengths must be positive.")
    if config.geometry.design_type == "flanged" and config.geometry.duct_flange_length <= 0:
        raise ValueError("Flange length must be positive.")
    mesh_sizes = [
        config.mesh.global_size_cm,
        config.mesh.growth_rate,
        config.mesh.resolution_size_cm,
        config.mesh.duct_size_cm,
        config.mesh.hub_size_cm,
    ]
    if config.mesh.inflation_enabled:
        mesh_sizes.append(config.mesh.inflation_max_thickness_cm)
    if min(mesh_sizes) <= 0:
        raise ValueError("All mesh sizes and inflation thickness must be positive.")
    if config.mesh.curvature_angle_deg <= 0:
        raise ValueError("Mesh curvature angle must be positive.")
    if config.mesh.cpu_cores is not None and config.mesh.cpu_cores < 1:
        raise ValueError("CPU cores for parallel part meshing must be at least one.")
    if config.mesh.method not in {"Default", "Quad", "Tri", "MultiZone"}:
        raise ValueError("Choose Default, Quad, Tri, or MultiZone as the meshing method.")
    if config.mesh.inflation_enabled and config.mesh.inflation_layers < 1:
        raise ValueError("Inflation must contain at least one layer.")
    if config.cfd.stations < 2 or config.cfd.max_outer_iterations < 1:
        raise ValueError("CFD stations and iteration counts are too small.")
    if min(config.cfd.flow_speed_m_s, config.cfd.density_kg_m3,
           config.cfd.viscosity_pa_s, config.cfd.rotor_radius_m) <= 0:
        raise ValueError("Flow properties and rotor radius must be positive.")
    if not 0 < config.cfd.hub_radius_m < config.cfd.rotor_radius_m:
        raise ValueError("Rotor hub radius must be positive and smaller than rotor radius.")
    if not 0 < config.cfd.relaxation <= 1:
        raise ValueError("CFD relaxation must be greater than 0 and no more than 1.")
    if (not math.isfinite(config.cfd.previous_source_weight)
            or not 0 <= config.cfd.previous_source_weight <= 1):
        raise ValueError("Previous-source weight must be a number from 0 to 1.")
    valid_cfd_choices = {
        name: set(values) for name, values in CFD_CHOICE_VALUES.items()
    }
    for name, options in valid_cfd_choices.items():
        if getattr(config.cfd, name) not in options:
            raise ValueError(f"Choose a valid CFD value for {name.replace('_', ' ')}.")
    active_residuals = ["residual_continuity", "residual_x_velocity", "residual_y_velocity",
                        "residual_swirl"]
    if config.cfd.viscous_model == "k_omega":
        active_residuals += ["residual_k", "residual_omega"]
    elif config.cfd.viscous_model == "k_epsilon":
        active_residuals += ["residual_k", "residual_epsilon"]
    else:
        active_residuals.append("residual_nut")
    if any(getattr(config.cfd, name) <= 0 for name in active_residuals):
        raise ValueError("Active Fluent residual criteria must be positive.")
