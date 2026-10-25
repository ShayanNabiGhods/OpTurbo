"""Standalone blade-element/momentum rotor performance calculations."""

from dataclasses import dataclass
import math

from .workflows.axisymmetric_2d.cfd.bem import _table, loss_factor
from .workflows.axisymmetric_2d.cfd.models import Airfoil, Blade, Flow, Performance, Turbine


@dataclass(frozen=True)
class SimpleBemResult:
    """Integrated rotor performance at one tip-speed ratio."""

    tip_speed_ratio: float
    omega_rad_s: float
    performance: Performance
    converged_stations: int
    station_count: int


def tsr_values(minimum: float, maximum: float, step: float) -> list[float]:
    """Return an inclusive, evenly spaced TSR sequence, with at most 101 points."""
    if not all(math.isfinite(value) for value in (minimum, maximum, step)):
        raise ValueError("TSR limits and interval must be finite numbers.")
    if minimum <= 0 or maximum < minimum or step <= 0:
        raise ValueError("TSR limits must be positive and ordered, and interval must be positive.")
    count = math.floor((maximum - minimum) / step + 1e-10) + 1
    if count > 101:
        raise ValueError("Choose an interval that produces no more than 101 TSR points.")
    return [minimum + index * step for index in range(count)]


def _annulus_solution(flow: Flow, turbine: Turbine, blade: Blade,
                      airfoil: Airfoil, index: int,
                      tolerance: float = 1e-5,
                      max_iterations: int = 250) -> tuple[float, float, float, float, float, bool]:
    """Iterate axial and tangential induction for one blade station."""
    radius = blade.radius[index]
    chord = blade.chord[index]
    twist = blade.twist[index]
    solidity = turbine.blades * chord / (2 * math.pi * radius)
    axial_induction = 0.2
    tangential_induction = 0.0
    converged = False

    for _ in range(max_iterations):
        phi = math.atan2(flow.speed * (1 - axial_induction),
                         turbine.omega * radius * (1 + tangential_induction))
        sine, cosine = math.sin(phi), math.cos(phi)
        if sine <= 1e-8 or cosine <= 1e-8:
            break
        loss = loss_factor(flow, turbine, radius, phi)
        angle = math.degrees(phi) - twist + turbine.pitch
        relative_speed = math.hypot(
            flow.speed * (1 - axial_induction),
            turbine.omega * radius * (1 + tangential_induction),
        )
        reynolds = flow.density * relative_speed * chord / flow.viscosity
        cl = _table(airfoil.alpha, airfoil.reynolds, airfoil.lift, angle, reynolds)
        cd = _table(airfoil.alpha, airfoil.reynolds, airfoil.drag, angle, reynolds)
        normal = cl * cosine + cd * sine
        tangential = cl * sine - cd * cosine

        if normal <= 1e-10:
            next_axial = 0.0
        else:
            denominator = 4 * loss * sine * sine / (solidity * normal) + 1
            next_axial = min(0.95, max(0.0, 1 / denominator))
        swirl_denominator = 4 * loss * sine * cosine / (solidity * tangential) - 1 \
            if abs(tangential) > 1e-10 else math.inf
        next_tangential = (min(1.0, max(-0.5, 1 / swirl_denominator))
                           if math.isfinite(swirl_denominator) and abs(swirl_denominator) > 1e-8
                           else 0.0)
        relaxed_axial = 0.7 * next_axial + 0.3 * axial_induction
        relaxed_tangential = 0.7 * next_tangential + 0.3 * tangential_induction
        if (abs(relaxed_axial - axial_induction) < tolerance and
                abs(relaxed_tangential - tangential_induction) < tolerance):
            axial_induction, tangential_induction = relaxed_axial, relaxed_tangential
            converged = True
            break
        axial_induction, tangential_induction = relaxed_axial, relaxed_tangential

    phi = math.atan2(flow.speed * (1 - axial_induction),
                     turbine.omega * radius * (1 + tangential_induction))
    sine, cosine = math.sin(phi), math.cos(phi)
    loss = loss_factor(flow, turbine, radius, phi)
    angle = math.degrees(phi) - twist + turbine.pitch
    relative_speed = math.hypot(
        flow.speed * (1 - axial_induction),
        turbine.omega * radius * (1 + tangential_induction),
    )
    reynolds = flow.density * relative_speed * chord / flow.viscosity
    cl = _table(airfoil.alpha, airfoil.reynolds, airfoil.lift, angle, reynolds)
    cd = _table(airfoil.alpha, airfoil.reynolds, airfoil.drag, angle, reynolds)
    normal = cl * cosine + cd * sine
    tangential = cl * sine - cd * cosine
    dynamic_force = 0.5 * flow.density * relative_speed ** 2 * turbine.blades * chord * loss
    thrust_per_span = dynamic_force * normal
    torque_per_span = dynamic_force * tangential * radius
    return axial_induction, tangential_induction, thrust_per_span, torque_per_span, loss, converged


def calculate_performance(flow: Flow, turbine: Turbine, blade: Blade,
                          airfoil: Airfoil) -> tuple[Performance, int]:
    """Solve the uncoupled BEM equations and integrate rotor loads."""
    if not all(math.isfinite(value) for value in (
            flow.speed, flow.density, flow.viscosity, turbine.radius,
            turbine.hub_radius, turbine.omega, turbine.pitch)):
        raise ValueError("Flow and rotor settings must be finite numbers.")
    if flow.speed <= 0 or flow.density <= 0 or flow.viscosity <= 0:
        raise ValueError("Wind speed, density, and viscosity must be positive.")
    if turbine.radius <= 0 or turbine.hub_radius < 0 or turbine.hub_radius >= turbine.radius:
        raise ValueError("Rotor radius must be positive and hub radius must be smaller than it.")
    if turbine.blades < 1 or turbine.omega <= 0:
        raise ValueError("Blade count and rotor angular speed must be positive.")
    if turbine.tip_loss_model not in {"prandtl", "bontempo2025"}:
        raise ValueError("Choose either the Prandtl or Bontempo 2025 loss correction.")
    if not all(math.isfinite(value) for value in (
            turbine.bontempo_g_a, turbine.bontempo_g_b, turbine.bontempo_g_c)):
        raise ValueError("Bontempo loss coefficients must be finite numbers.")
    if len(blade.radius) < 2 or not (len(blade.radius) == len(blade.chord) == len(blade.twist) == len(blade.dr)):
        raise ValueError("Blade data must contain matching arrays with at least two stations.")
    if any(not math.isfinite(value) for values in (blade.radius, blade.chord, blade.twist, blade.dr)
           for value in values):
        raise ValueError("Blade geometry values must be finite numbers.")
    if any(value <= 0 for values in (blade.radius, blade.chord, blade.dr) for value in values):
        raise ValueError("Blade radii, chord lengths, and station widths must be positive.")
    if any(next_radius <= radius for radius, next_radius in zip(blade.radius, blade.radius[1:])):
        raise ValueError("Blade radial stations must be in strictly increasing order.")
    if blade.radius[0] < turbine.hub_radius - 1e-9 or blade.radius[-1] > turbine.radius + 1e-9:
        raise ValueError("Blade geometry must lie between the selected hub and rotor tip.")

    station_results = [
        _annulus_solution(flow, turbine, blade, airfoil, index)
        for index in range(len(blade.radius))
    ]
    thrust = 0.0
    torque = 0.0
    for index, (radius, width, result) in enumerate(zip(blade.radius, blade.dr, station_results)):
        # Trapezoidal end weights keep the supplied radial station data well behaved.
        weight = 0.5 if index in {0, len(blade.radius) - 1} else 1.0
        thrust += weight * result[2] * width
        torque += weight * result[3] * width
    power = turbine.omega * torque
    swept_area = math.pi * turbine.radius ** 2
    cp = power / (0.5 * flow.density * swept_area * flow.speed ** 3)
    ct = thrust / (0.5 * flow.density * swept_area * flow.speed ** 2)
    return Performance(thrust, torque, power, cp, ct), sum(item[-1] for item in station_results)


def run_tsr_sweep(flow: Flow, turbine: Turbine, blade: Blade,
                  airfoil: Airfoil, minimum: float, maximum: float,
                  step: float) -> list[SimpleBemResult]:
    """Run standalone BEM at each TSR by deriving rotor speed from TSR = ωR/U."""
    if not math.isfinite(flow.speed) or flow.speed <= 0:
        raise ValueError("Free-stream speed must be a positive finite number.")
    if not math.isfinite(turbine.radius) or turbine.radius <= 0:
        raise ValueError("Rotor radius must be a positive finite number.")
    results = []
    for tsr in tsr_values(minimum, maximum, step):
        operating_turbine = Turbine(
            radius=turbine.radius,
            hub_radius=turbine.hub_radius,
            blades=turbine.blades,
            omega=tsr * flow.speed / turbine.radius,
            pitch=turbine.pitch,
            tip_loss_model=turbine.tip_loss_model,
            bontempo_g_a=turbine.bontempo_g_a,
            bontempo_g_b=turbine.bontempo_g_b,
            bontempo_g_c=turbine.bontempo_g_c,
        )
        performance, converged = calculate_performance(flow, operating_turbine, blade, airfoil)
        results.append(SimpleBemResult(tsr, operating_turbine.omega, performance,
                                       converged, len(blade.radius)))
    return results
