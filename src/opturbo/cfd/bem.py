"""Blade-element momentum calculations used by the coupling driver."""

import math
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


def solve(flow, turbine, blade, airfoil, axial, tangential):
    """Calculate induction, angles, airfoil loads, and BEM loads."""
    values = [[] for _ in range(8)]
    for radius, chord, twist, ua, ut in zip(blade.radius, blade.chord, blade.twist, axial, tangential):
        a = 1 - ua / flow.speed
        ap = -ut / (turbine.omega * radius)
        phi = math.atan2(1 - a, turbine.omega * radius / flow.speed * (1 + ap))
        sine, cosine = math.sin(phi), math.cos(phi)
        tip = turbine.blades / 2 * (turbine.radius - radius) / (radius * sine)
        root = turbine.blades / 2 * (radius - turbine.hub_radius) / (radius * sine)
        tip_loss = 2 / math.pi * math.acos(math.exp(-tip))
        root_loss = 2 / math.pi * math.acos(math.exp(-root))
        loss = max(1e-4, tip_loss * root_loss)
        angle = math.degrees(phi) - twist + turbine.pitch
        speed = math.sqrt((flow.speed * (1 - a)) ** 2 +
                          (turbine.omega * radius * (1 + ap)) ** 2)
        reynolds_value = flow.density * speed * chord / flow.viscosity
        cl = _table(airfoil.alpha, airfoil.reynolds, airfoil.lift, angle, reynolds_value)
        cd = _table(airfoil.alpha, airfoil.reynolds, airfoil.drag, angle, reynolds_value)
        normal = cl * cosine + cd * sine
        tangential = cl * sine - cd * cosine
        solidity = turbine.blades * chord / (2 * math.pi * radius)
        fn = -0.5 * flow.density * speed ** 2 * solidity * normal * loss / blade.thickness
        ft = 0.5 * flow.density * speed ** 2 * solidity * tangential * loss / blade.thickness
        for target, item in zip(values, (a, ap, math.degrees(phi), angle, reynolds_value, loss, fn, ft)):
            target.append(item)
    return Results(*values)


def sources_from(results):
    """Convert blade loads into equal-and-opposite fluid sources."""
    return Sources(results.dT[:], [-value for value in results.dQ])


def performance(flow, turbine, blade, results):
    """Integrate radial loads using each station's actual width."""
    thrust = sum(2 * math.pi * r * dr * blade.thickness * load
                 for r, dr, load in zip(blade.radius, blade.dr, results.dT))
    torque = sum(r * 2 * math.pi * r * dr * blade.thickness * load
                 for r, dr, load in zip(blade.radius, blade.dr, results.dQ))
    power = turbine.omega * torque
    area = math.pi * turbine.radius ** 2
    cp = power / (0.5 * flow.density * area * flow.speed ** 3)
    ct = -thrust / (0.5 * flow.density * area * flow.speed ** 2)
    return Performance(thrust, torque, power, cp, ct)
