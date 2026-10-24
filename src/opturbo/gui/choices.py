"""Allowed values and field groups used by workflow settings forms."""

from ..domain.choices import CFD_CHOICE_VALUES

CPU_CORE_CHOICES = ("Program Controlled", *(str(value) for value in range(1, 129)))

MESH_STUDY_SIZE_FIELDS = {
    "global_size_cm", "growth_rate", "curvature_angle_deg", "resolution_size_cm",
    "duct_size_cm", "hub_size_cm", "inflation_layers", "inflation_max_thickness_cm",
}

TURBULENCE_EQUATIONS = {
    "k_omega": ("k", "omega"),
    "k_epsilon": ("k", "epsilon"),
    "spalart_allmaras": ("nut",),
}

TURBULENCE_FIELDS = {"viscous_model"} | {
    name for equation in ("k", "omega", "epsilon", "nut")
    for name in (f"residual_{equation}", f"{equation}_scheme")
}
