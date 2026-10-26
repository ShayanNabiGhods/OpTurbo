"""Read and validate the numeric tables used by BEM and CFD coupling."""

import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .models import Airfoil, Blade, Flow, Turbine


CFD_TABLE_FILES = (
    "ntnu_geometry.csv",
    "s826_alpha.csv",
    "s826_re.csv",
    "s826_cl.csv",
    "s826_cd.csv",
)


def read_numeric_csv(path: str | Path) -> list[list[float]]:
    """Read a headerless, rectangular CSV of finite numeric values."""
    source = Path(path)
    rows: list[list[float]] = []
    try:
        with source.open(encoding="utf-8-sig", newline="") as handle:
            for line_number, row in enumerate(csv.reader(handle), start=1):
                if not row or not any(value.strip() for value in row):
                    continue
                try:
                    values = [float(value.strip()) for value in row]
                except ValueError as error:
                    raise ValueError(
                        f"{source.name}, row {line_number}: enter numbers only; do not add a header."
                    ) from error
                if not all(math.isfinite(value) for value in values):
                    raise ValueError(f"{source.name}, row {line_number}: values must be finite numbers.")
                if rows and len(values) != len(rows[0]):
                    raise ValueError(f"{source.name}, row {line_number}: every row must have the same number of columns.")
                rows.append(values)
    except csv.Error as error:
        raise ValueError(f"{source.name}: invalid CSV syntax ({error}).") from error
    if not rows:
        raise ValueError(f"{source.name}: the CSV must contain numeric data.")
    return rows


def numbers(path: str | Path) -> list[list[float]]:
    """Keep the historic CSV-reader name for compatibility imports."""
    return read_numeric_csv(path)


def validate_geometry_table(rows: Sequence[Sequence[float]]) -> None:
    """Check radius, chord, and twist values for at least two blade sections."""
    if len(rows) < 2 or any(len(row) != 3 for row in rows):
        raise ValueError("ntnu_geometry.csv needs at least two rows with exactly 3 columns: radius, chord, twist.")
    radii = [row[0] for row in rows]
    if any(radius <= 0 for radius in radii):
        raise ValueError("Blade section radii must be positive metres.")
    if any(right <= left for left, right in zip(radii, radii[1:])):
        raise ValueError("Blade section radii must increase strictly from hub to tip.")
    if any(row[1] <= 0 for row in rows):
        raise ValueError("Blade chord values must be positive metres.")


def _one_column(values: Sequence[Sequence[float]], filename: str, minimum: int) -> list[float]:
    """Validate and flatten a one-column table."""
    if len(values) < minimum or any(len(row) != 1 for row in values):
        raise ValueError(f"{filename} must contain at least {minimum} rows and exactly one value per row.")
    return [row[0] for row in values]


def validate_airfoil_tables(
    alpha_rows: Sequence[Sequence[float]],
    reynolds_rows: Sequence[Sequence[float]],
    lift_rows: Sequence[Sequence[float]],
    drag_rows: Sequence[Sequence[float]],
) -> tuple[list[float], list[float]]:
    """Validate polar dimensions and return the alpha and Reynolds axes."""
    alpha = _one_column(alpha_rows, "s826_alpha.csv", 2)
    if len(reynolds_rows) != 1 or len(reynolds_rows[0]) < 2:
        raise ValueError("s826_re.csv must contain one row with at least two Reynolds numbers.")
    reynolds = list(reynolds_rows[0])
    if any(value <= 0 for value in reynolds):
        raise ValueError("Reynolds numbers must be positive.")
    if any(right <= left for left, right in zip(alpha, alpha[1:])):
        raise ValueError("s826_alpha.csv angles must increase strictly.")
    if any(right <= left for left, right in zip(reynolds, reynolds[1:])):
        raise ValueError("s826_re.csv Reynolds numbers must increase strictly.")
    expected_rows, expected_columns = len(alpha), len(reynolds)
    for filename, matrix in (("s826_cl.csv", lift_rows), ("s826_cd.csv", drag_rows)):
        if len(matrix) != expected_rows or any(len(row) != expected_columns for row in matrix):
            raise ValueError(
                f"{filename} must have {expected_rows} rows (one per angle) and "
                f"{expected_columns} columns (one per Reynolds number)."
            )
    if any(value < 0 for row in drag_rows for value in row):
        raise ValueError("s826_cd.csv drag coefficients must be zero or positive.")
    return alpha, reynolds


def validate_cfd_tables(tables: Mapping[str, Sequence[Sequence[float]]]) -> None:
    """Validate all five related tables before saving an edited/imported set."""
    missing = [name for name in CFD_TABLE_FILES if name not in tables]
    if missing:
        raise ValueError("Missing CFD table(s): " + ", ".join(missing))
    validate_geometry_table(tables["ntnu_geometry.csv"])
    validate_airfoil_tables(
        tables["s826_alpha.csv"], tables["s826_re.csv"],
        tables["s826_cl.csv"], tables["s826_cd.csv"],
    )


def write_numeric_csv(path: str | Path, rows: Sequence[Sequence[float]]) -> None:
    """Write a numeric table with stable precision and standard CSV quoting."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows([[format(float(value), ".15g") for value in row] for row in rows])


def load_airfoil(folder: str | Path) -> Airfoil:
    """Load and cross-check angle, Reynolds, lift, and drag tables."""
    root = Path(folder)
    alpha_rows = read_numeric_csv(root / "s826_alpha.csv")
    reynolds_rows = read_numeric_csv(root / "s826_re.csv")
    lift_rows = read_numeric_csv(root / "s826_cl.csv")
    drag_rows = read_numeric_csv(root / "s826_cd.csv")
    alpha, reynolds = validate_airfoil_tables(alpha_rows, reynolds_rows, lift_rows, drag_rows)
    # Solver lookup arrays are [Reynolds index][angle index].
    lift = [list(column) for column in zip(*lift_rows)]
    drag = [list(column) for column in zip(*drag_rows)]
    return Airfoil(alpha, reynolds, lift, drag)


def _linear(x: Sequence[float], y: Sequence[float], value: float) -> float:
    """Linearly interpolate one value, clamping outside the table."""
    if value <= x[0]:
        return y[0]
    for index in range(1, len(x)):
        if value <= x[index]:
            fraction = (value - x[index - 1]) / (x[index] - x[index - 1])
            return y[index - 1] + fraction * (y[index] - y[index - 1])
    return y[-1]


def load_blade(
    folder: str | Path,
    stations: int | None = 36,
    thickness: float = 0.005,
) -> Blade:
    """Load blade sections and optionally resample them to a requested count."""
    rows = read_numeric_csv(Path(folder) / "ntnu_geometry.csv")
    validate_geometry_table(rows)
    if stations is not None and (not isinstance(stations, int) or isinstance(stations, bool) or stations < 2):
        raise ValueError("BEM radial station count must be a whole number of at least two, or None to use CSV rows.")
    radius, chord, twist = zip(*rows)
    if stations is None or stations == len(rows):
        new_radius, new_chord, new_twist = list(radius), list(chord), list(twist)
    else:
        step = (radius[-1] - radius[0]) / (stations - 1)
        new_radius = [radius[0] + index * step for index in range(stations)]
        new_chord = [_linear(radius, chord, value) for value in new_radius]
        new_twist = [_linear(radius, twist, value) for value in new_radius]
    dr = [new_radius[index + 1] - new_radius[index] for index in range(len(new_radius) - 1)]
    dr.append(dr[-1])
    return Blade(new_radius, new_chord, new_twist, dr, thickness)


def load_setup(folder: str | Path) -> tuple[Flow, Turbine]:
    """Load workflow metadata and return flow and turbine objects."""
    data = json.loads(Path(folder, "metadata.json").read_text(encoding="utf-8"))
    flow = Flow(data["flow_speed_m_s"], data["density_kg_m3"], data["viscosity_pa_s"])
    turbine = Turbine(data["rotor_radius_m"], data["hub_radius_m"],
                      data["blades"], data["omega_rad_s"], data["pitch_deg"])
    return flow, turbine
