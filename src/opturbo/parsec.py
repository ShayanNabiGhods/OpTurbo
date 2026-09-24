"""Dependency-free PARSEC calculations used by previews and validation."""

from __future__ import annotations

import math

from .models import VariableSpec


def nested_parameters(variables: list[VariableSpec]) -> dict[str, dict[str, float]]:
    """Extract upper/lower PARSEC dictionaries from all design variables."""
    result: dict[str, dict[str, float]] = {"upper": {}, "lower": {}}
    for variable in variables:
        side, name = variable.key.split(".", 1)
        if side in result:
            result[side][name] = variable.value
    return result



def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve a small dense system by pivoted Gaussian elimination."""
    rows = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for pivot in range(len(rhs)):
        best = max(range(pivot, len(rows)), key=lambda row: abs(rows[row][pivot]))
        rows[pivot], rows[best] = rows[best], rows[pivot]
        scale = rows[pivot][pivot]
        if abs(scale) < 1e-14:
            raise ValueError("The PARSEC coefficient system is singular.")
        rows[pivot] = [value / scale for value in rows[pivot]]
        for row_index, row in enumerate(rows):
            if row_index == pivot:
                continue
            factor = row[pivot]
            rows[row_index] = [a - factor * b for a, b in zip(row, rows[pivot])]
    return [row[-1] for row in rows]


def coefficients(side: dict[str, float], sign: float) -> list[float]:
    """Calculate the six coefficients for one PARSEC surface."""
    powers = [index - 0.5 for index in range(1, 7)]
    first = sign * math.sqrt(2.0 * side["leading_edge_radius"])
    x = side["crest_location"]
    matrix = [
        [1.0 for _ in powers[1:]],
        [power for power in powers[1:]],
        [x**power for power in powers[1:]],
        [power * x ** (power - 1) for power in powers[1:]],
        [power * (power - 1) * x ** (power - 2) for power in powers[1:]],
    ]
    rhs = [
        side["trailing_edge_height"] - first,
        math.tan(math.radians(side["trailing_edge_slope_deg"])) - first * powers[0],
        side["crest_height"] - first * x ** powers[0],
        -first * powers[0] * x ** (powers[0] - 1),
        side["crest_curvature"] - first * powers[0] * (powers[0] - 1) * x ** (powers[0] - 2),
    ]
    return [first, *_solve(matrix, rhs)]


def profile(parameters: dict[str, dict[str, float]], points: int = 180) -> tuple[list[float], list[float], list[float]]:
    """Return normalized x, upper y, and lower y coordinates."""
    if points < 10:
        raise ValueError("At least 10 duct points are required.")
    x_values = [index / (points - 1) for index in range(points)]
    upper_coefficients = coefficients(parameters["upper"], 1.0)
    lower_coefficients = coefficients(parameters["lower"], -1.0)

    def surface(x: float, values: list[float]) -> float:
        return sum(value * x ** (index + 0.5) for index, value in enumerate(values))

    return (
        x_values,
        [surface(x, upper_coefficients) for x in x_values],
        [surface(x, lower_coefficients) for x in x_values],
    )


def validate_profile(parameters: dict[str, dict[str, float]]) -> None:
    """Reject obviously invalid or self-intersecting duct profiles."""
    for side in ("upper", "lower"):
        values = parameters[side]
        if values["leading_edge_radius"] <= 0:
            raise ValueError(f"{side} leading-edge radius must be positive.")
        if not 0 < values["crest_location"] < 1:
            raise ValueError(f"{side} crest location must lie between 0 and 1.")
    _, upper, lower = profile(parameters, 120)
    minimum_thickness = min(a - b for a, b in zip(upper[1:-1], lower[1:-1]))
    if minimum_thickness <= 1e-5:
        raise ValueError("The upper and lower PARSEC surfaces intersect.")
