"""Blade-element momentum calculations used by the coupling driver."""

import math
from collections.abc import Sequence

from .models import Airfoil, Blade, Flow, Performance, Results, Sources, Turbine


def _table(alpha, reynolds, table, angle, reynolds_value):
    """Bilinearly interpolate a table and clamp outside its domain."""
    angle = min(max(angle, alpha[0]), alpha[-1])
    reynolds_value = min(max(reynolds_value, reynolds[0]), reynolds[-1])
    ai = next((i for i, value in enumerate(alpha) if value >= angle), len(alpha) - 1)
    ri = next((i for i, value in enumerate(reynolds) if value >= reynolds_value), len(reynolds) - 1)
    ai, ri = max(1, ai), max(1, ri)
    a0, a1 = alpha[ai - 1], alpha[ai]
    r0, r1 = reynolds[ri - 1], reynolds[ri]
    ta = (angle - a0) / (a1 - a0)
    tr = (reynolds_value - r0) / (r1 - r0)
    q00, q01 = table[ri - 1][ai - 1], table[ri - 1][ai]
    q10, q11 = table[ri][ai - 1], table[ri][ai]
    return q00 * (1 - ta) * (1 - tr) + q01 * ta * (1 - tr) + q10 * (1 - ta) * tr + q11 * ta * tr


def loss_factor(flow: Flow, turbine: Turbine, radius: float, phi: float) -> float:
    """Return a tip correction multiplied by the Prandtl root-loss factor.

    Bontempo & Manna (2025), p. 5, Eq. (6), supplies only the duct-calibrated
    tip correction. Its lambda is the rotor tip-speed ratio, not the local
    ratio; root loss remains the conventional Prandtl factor.
    """
    if turbine.tip_loss_model not in {"prandtl", "bontempo2025"}:
        raise ValueError("Unknown tip-loss model: " + turbine.tip_loss_model)
    if not turbine.hub_radius <= radius <= turbine.radius or radius <= 0:
        raise ValueError("Blade stations must lie between the hub and rotor tip.")
    sine = math.sin(phi)
    if not math.isfinite(sine) or sine <= 0:
        raise ValueError("Tip-loss correction requires a positive inflow-angle sine.")
    tip_argument = turbine.blades / 2 * (turbine.radius - radius) / (radius * sine)
    root_argument = turbine.blades / 2 * (radius - turbine.hub_radius) / (radius * sine)
    # bontempo2025 tip-loss factor
    if turbine.tip_loss_model == "bontempo2025":
        if flow.speed <= 0 or turbine.omega < 0:
            raise ValueError("Bontempo correction requires positive wind speed and nonnegative rotor speed.")
        tip_speed_ratio = turbine.omega * turbine.radius / flow.speed
        g = math.exp(turbine.bontempo_g_a *
                     (turbine.blades * tip_speed_ratio - turbine.bontempo_g_b)) + turbine.bontempo_g_c
        tip_loss = 2 / math.pi * math.acos(math.exp(-g * tip_argument))
    else:
        tip_loss = 2 / math.pi * math.acos(math.exp(-tip_argument))
    root_loss = 2 / math.pi * math.acos(math.exp(-root_argument))
    return max(1e-4, tip_loss * root_loss)


def solve(
    flow: Flow,
    turbine: Turbine,
    blade: Blade,
    airfoil: Airfoil,
    axial: Sequence[float],
    tangential: Sequence[float],
) -> Results:
    """Calculate induction, angles, airfoil loads, and BEM loads."""
    station_count = len(blade.radius)
    if station_count < 1 or any(len(values) != station_count for values in (
        blade.chord, blade.twist, blade.dr, axial, tangential
    )):
        raise ValueError("Blade geometry and Fluent velocity arrays must have the same count of one or more stations.")
    if (len(airfoil.alpha) < 2 or len(airfoil.reynolds) < 2 or
            len(airfoil.lift) != len(airfoil.reynolds) or
            len(airfoil.drag) != len(airfoil.reynolds) or
            any(len(row) != len(airfoil.alpha) for matrix in (airfoil.lift, airfoil.drag) for row in matrix)):
        raise ValueError("Airfoil lift/drag tables must match their angle and Reynolds axes.")
    values = [[] for _ in range(8)]
    for radius, chord, twist, ua, ut in zip(blade.radius, blade.chord, blade.twist, axial, tangential):
        a = 1 - ua / flow.speed
        ap = -ut / (turbine.omega * radius)
        phi = math.atan2(1 - a, turbine.omega * radius / flow.speed * (1 + ap))
        sine, cosine = math.sin(phi), math.cos(phi)
        loss = loss_factor(flow, turbine, radius, phi)
        angle = math.degrees(phi) - twist + turbine.pitch
        speed = math.sqrt((flow.speed * (1 - a)) ** 2 +
                          (turbine.omega * radius * (1 + ap)) ** 2)
        reynolds_value = flow.density * speed * chord / flow.viscosity
        cl = _table(airfoil.alpha, airfoil.reynolds, airfoil.lift, angle, reynolds_value)
        cd = _table(airfoil.alpha, airfoil.reynolds, airfoil.drag, angle, reynolds_value)
        normal = cl * cosine + cd * sine
        tangential_coefficient = cl * sine - cd * cosine
        solidity = turbine.blades * chord / (2 * math.pi * radius)
        fn = -0.5 * flow.density * speed ** 2 * solidity * normal * loss / blade.thickness
        ft = 0.5 * flow.density * speed ** 2 * solidity * tangential_coefficient * loss / blade.thickness
        for target, item in zip(values, (a, ap, math.degrees(phi), angle, reynolds_value, loss, fn, ft)):
            target.append(item)
    return Results(*values)


def sources_from(results: Results) -> Sources:
    """Convert blade loads into equal-and-opposite fluid sources."""
    return Sources(results.dT[:], [-value for value in results.dQ])


def performance(flow: Flow, turbine: Turbine, blade: Blade, results: Results) -> Performance:
    """Integrate radial loads using each station's actual width."""
    station_count = len(blade.radius)
    if station_count < 2 or any(len(values) != station_count for values in (
        blade.dr, results.dT, results.dQ
    )):
        raise ValueError("Blade spacing and BEM load arrays must match the radial station count.")
    thrust = sum(2 * math.pi * r * dr * blade.thickness * load
                 for r, dr, load in zip(blade.radius, blade.dr, results.dT))
    torque = sum(r * 2 * math.pi * r * dr * blade.thickness * load
                 for r, dr, load in zip(blade.radius, blade.dr, results.dQ))
    power = turbine.omega * torque
    area = math.pi * turbine.radius ** 2
    cp = power / (0.5 * flow.density * area * flow.speed ** 3)
    ct = -thrust / (0.5 * flow.density * area * flow.speed ** 2)
    return Performance(thrust, torque, power, cp, ct)
