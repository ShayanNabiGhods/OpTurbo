"""Load readable CSV/JSON resources and build model objects."""

import csv
import json
from pathlib import Path
from .models import Airfoil, Blade, Flow, Turbine


def numbers(path):
    """Read a CSV file containing one numeric row or a numeric matrix."""
    with Path(path).open() as handle:
        return [[float(value) for value in row] for row in csv.reader(handle)
                if row and any(value.strip() for value in row)]


def load_airfoil(folder):
    """Load S826 angle, Reynolds, lift, and drag tables."""
    root = Path(folder)
    alpha = [row[0] for row in numbers(root / "s826_alpha.csv")]
    reynolds = numbers(root / "s826_re.csv")[0]
    lift = numbers(root / "s826_cl.csv")
    drag = numbers(root / "s826_cd.csv")
    lift = [list(column) for column in zip(*lift)]
    drag = [list(column) for column in zip(*drag)]
    return Airfoil(alpha, reynolds, lift, drag)


def _linear(x, y, value):
    """Linearly interpolate one value, clamping outside the table."""
    if value <= x[0]:
        return y[0]
    for i in range(1, len(x)):
        if value <= x[i]:
            fraction = (value - x[i - 1]) / (x[i] - x[i - 1])
            return y[i - 1] + fraction * (y[i] - y[i - 1])
    return y[-1]


def load_blade(folder, stations=36, thickness=0.005):
    """Interpolate the reference blade onto the requested stations."""
    rows = numbers(Path(folder) / "ntnu_geometry.csv")
    radius, chord, twist = zip(*rows)
    if stations == 27:
        new_radius, new_chord, new_twist = list(radius), list(chord), list(twist)
    else:
        step = (radius[-1] - radius[0]) / (stations - 1)
        new_radius = [radius[0] + i * step for i in range(stations)]
        new_chord = [_linear(radius, chord, value) for value in new_radius]
        new_twist = [_linear(radius, twist, value) for value in new_radius]
    dr = [new_radius[i + 1] - new_radius[i] for i in range(len(new_radius) - 1)]
    dr.append(dr[-1])
    return Blade(new_radius, new_chord, new_twist, dr, thickness)


def load_setup(folder):
    """Load metadata and return flow and turbine objects."""
    data = json.loads(Path(folder, "metadata.json").read_text())
    flow = Flow(data["flow_speed_m_s"], data["density_kg_m3"],
                data["viscosity_pa_s"])
    turbine = Turbine(data["rotor_radius_m"], data["hub_radius_m"],
                      data["blades"], data["omega_rad_s"], data["pitch_deg"])
    return flow, turbine
