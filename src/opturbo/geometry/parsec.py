"""Small PARSEC airfoil generator used by the single duct profile."""

import math


def coefficients(side: dict, sign: float) -> list[float]:
    """Solve the six PARSEC coefficients for one airfoil surface."""
    p = [i - 0.5 for i in range(1, 7)]
    a1 = sign * math.sqrt(2 * side["leading_edge_radius"])
    x, z, curvature = side["crest_location"], side["crest_height"], side["crest_curvature"]
    slope = math.tan(math.radians(side["trailing_edge_slope_deg"]))
    matrix = [
        [1 for power in p[1:]],
        [power for power in p[1:]],
        [x**power for power in p[1:]],
        [power * x**(power - 1) for power in p[1:]],
        [power * (power - 1) * x**(power - 2) for power in p[1:]],
    ]
    rhs = [side["trailing_edge_height"] - a1,
           slope - a1 * p[0], z - a1 * x**p[0],
           -a1 * p[0] * x**(p[0] - 1),
           curvature - a1 * p[0] * (p[0] - 1) * x**(p[0] - 2)]
    return [a1, *solve_system(matrix, rhs)]


def solve_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve a small dense system with pivoted Gaussian elimination."""
    rows = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for pivot in range(len(rhs)):
        best = max(range(pivot, len(rows)), key=lambda i: abs(rows[i][pivot]))
        rows[pivot], rows[best] = rows[best], rows[pivot]
        scale = rows[pivot][pivot]
        if abs(scale) < 1e-14:
            raise ValueError("PARSEC coefficient system is singular.")
        rows[pivot] = [value / scale for value in rows[pivot]]
        for row in range(len(rows)):
            if row != pivot:
                factor = rows[row][pivot]
                rows[row] = [a - factor * b for a, b in zip(rows[row], rows[pivot])]
    return [row[-1] for row in rows]


def surface(x: float, values: list[float]) -> float:
    """Evaluate one PARSEC surface at normalized chord position x."""
    return sum(value * x ** (index + 0.5) for index, value in enumerate(values))


def profile(points: int, parsec: dict) -> tuple[list[float], list[float]]:
    """Return normalized x coordinates and upper/lower PARSEC ordinates."""
    x_values = [i / (points - 1) for i in range(points)]
    upper = coefficients(parsec["upper"], 1)
    lower = coefficients(parsec["lower"], -1)
    return x_values, [surface(x, upper) for x in x_values], [surface(x, lower) for x in x_values]
