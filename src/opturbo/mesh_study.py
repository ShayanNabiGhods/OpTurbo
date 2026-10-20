"""Candidate generation and mesh-count extraction for mesh-study runs."""

from __future__ import annotations

from dataclasses import replace

from .models import MeshSettings


_FIELDS = (
    "global_size_cm", "growth_rate", "curvature_angle_deg", "resolution_size_cm",
    "duct_size_cm", "hub_size_cm", "inflation_layers", "inflation_max_thickness_cm",
)
_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19)


def _halton(index: int, base: int) -> float:
    """Return one deterministic Halton-sequence value in [0, 1)."""
    result, fraction = 0.0, 1.0 / base
    while index:
        result += fraction * (index % base)
        index //= base
        fraction /= base
    return result


def mesh_variable_bounds(settings: MeshSettings) -> dict[str, tuple[float, float]]:
    """Build useful screening ranges around the current mesh settings."""
    return {
        "global_size_cm": (settings.global_size_cm * 0.6, settings.global_size_cm * 1.5),
        "growth_rate": (max(1.01, settings.growth_rate - 0.10), min(1.5, settings.growth_rate + 0.10)),
        "curvature_angle_deg": (max(1.0, settings.curvature_angle_deg * 0.6),
                                min(15.0, settings.curvature_angle_deg * 1.6)),
        "resolution_size_cm": (settings.resolution_size_cm * 0.5, settings.resolution_size_cm * 1.8),
        "duct_size_cm": (settings.duct_size_cm * 0.5, settings.duct_size_cm * 1.8),
        "hub_size_cm": (settings.hub_size_cm * 0.5, settings.hub_size_cm * 1.8),
        "inflation_layers": (float(max(1, settings.inflation_layers - 2)),
                             float(settings.inflation_layers + 3)),
        "inflation_max_thickness_cm": (settings.inflation_max_thickness_cm * 0.5,
                                       settings.inflation_max_thickness_cm * 1.8),
    }


def automatic_mesh_settings(
    base: MeshSettings, count: int, method: str, enabled_fields: set[str] | None = None,
    bounds: dict[str, tuple[float, float]] | None = None,
) -> list[MeshSettings]:
    """Build a baseline, one-factor screening cases, then space-filling cases."""
    if count < 1:
        raise ValueError("An automatic mesh sweep must include at least one case.")
    selected_method = "Default" if method == "Default (ANSYS automatic)" else method
    baseline = replace(base, method=selected_method)
    candidates = [baseline]
    bounds = bounds or mesh_variable_bounds(base)
    variable_names = [name for name in _FIELDS if enabled_fields is None or name in enabled_fields]

    # Screen each variable at its low and high range while holding others fixed.
    for name in variable_names:
        low, high = bounds[name]
        for value in (low, high):
            if len(candidates) >= count:
                return candidates
            if name == "inflation_layers":
                value = int(round(value))
            candidates.append(replace(baseline, **{name: value}))

    # Add low-discrepancy combinations to explore interactions between sizes.
    sequence_index = 1
    while len(candidates) < count:
        values = {}
        for name, prime in zip(variable_names, _PRIMES):
            low, high = bounds[name]
            fraction = _halton(sequence_index, prime)
            value = low + fraction * (high - low)
            values[name] = int(round(value)) if name == "inflation_layers" else value
        sequence_index += 1
        candidates.append(replace(baseline, **values))
    return candidates


def mesh_cell_count(mesh_path, log_paths=()) -> int | None:
    """Read the total cell count from Workbench/Fluent logs or ASCII Fluent mesh headers."""
    import re
    from pathlib import Path

    patterns = (
        re.compile(r"\bOPTURBO_MESH_CELL_COUNT\s*=\s*([\d,]+)", re.IGNORECASE),
        re.compile(r"\bnumber\s+of\s+cells\s*[:=]\s*([\d,]+)", re.IGNORECASE),
        re.compile(r"\btotal\s+cells\s*[:=]\s*([\d,]+)", re.IGNORECASE),
        re.compile(r"\b([\d,]+)\s+cells\b", re.IGNORECASE),
        re.compile(r"\bnumber\s+of\s+elements\s*[:=]\s*([\d,]+)", re.IGNORECASE),
    )
    for path in log_paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        counts = [int(match.replace(",", "")) for pattern in patterns for match in pattern.findall(text)]
        if counts:
            return max(counts)

    try:
        with Path(mesh_path).open("rb") as handle:
            header = handle.read(8 * 1024 * 1024).decode("ascii", errors="ignore")
    except OSError:
        return None
    # Fluent legacy mesh cell-zone headers: (12 (zone first-cell last-cell ...)).
    zones = re.findall(r"\(\s*12\s*\(\s*(\w+)\s+(\w+)\s+(\w+)\s+\d+", header)
    counts = []
    for zone, first, last in zones:
        if zone == "0":
            continue
        try:
            first_index, last_index = int(first, 16), int(last, 16)
        except ValueError:
            continue
        if last_index >= first_index:
            counts.append(last_index - first_index + 1)
    return sum(counts) if counts else None
