"""Valid solver values shared by workflow validation and settings forms."""

CFD_CHOICE_VALUES = {
    "viscous_model": ("k_omega", "k_epsilon", "spalart_allmaras"),
    "pressure_scheme": ("second_order", "standard", "presto", "linear",
                        "body_force_weighted"),
    "momentum_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                        "third_order_muscl"),
    "swirl_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                     "third_order_muscl"),
    "k_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                 "third_order_muscl"),
    "epsilon_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                       "third_order_muscl"),
    "omega_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                     "third_order_muscl"),
    "nut_scheme": ("first_order_upwind", "second_order_upwind", "quick",
                   "third_order_muscl"),
    "pressure_velocity_coupling": ("simple", "simplec", "piso", "coupled"),
    "source_initialization": ("conservative", "previous_candidate"),
}
