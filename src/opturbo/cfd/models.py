"""Small data containers used by the beginner-friendly BEM port."""

from dataclasses import dataclass


@dataclass
class Flow:
    """Free-stream air properties."""
    speed: float
    density: float
    viscosity: float


@dataclass
class Turbine:
    """Rotor geometry and operating point."""
    radius: float
    hub_radius: float
    blades: int
    omega: float
    pitch: float = 0.0


@dataclass
class Blade:
    """Radial stations and local blade geometry."""
    radius: list[float]
    chord: list[float]
    twist: list[float]
    dr: list[float]
    thickness: float


@dataclass
class Airfoil:
    """Lift and drag tables indexed by Reynolds number and angle."""
    alpha: list[float]
    reynolds: list[float]
    lift: list[list[float]]
    drag: list[list[float]]


@dataclass
class Results:
    """One BEM evaluation at all radial stations."""
    a: list[float]
    ap: list[float]
    phi: list[float]
    alpha: list[float]
    reynolds: list[float]
    loss: list[float]
    dT: list[float]
    dQ: list[float]


@dataclass
class Performance:
    """Integrated rotor loads and nondimensional coefficients."""
    thrust: float
    torque: float
    power: float
    cp: float
    ct: float


@dataclass
class Sources:
    """Axial and tangential momentum sources for Fluent."""
    axial: list[float]
    tangential: list[float]
