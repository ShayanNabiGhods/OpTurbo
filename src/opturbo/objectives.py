"""Optimization objective selection and candidate fitness extraction."""

import math
from collections.abc import Mapping


OBJECTIVES = {
    "cp": "Cp",
    "ct": "Ct",
    "cp_normalized": "Cp (duct-tip normalized)",
    "ct_normalized": "Ct (duct-tip normalized)",
}


def objective_value(result: Mapping[str, object], objective: str) -> float:
    """Return a finite GA fitness for the configured objective."""
    if objective not in OBJECTIVES:
        raise ValueError(f"Unknown optimization objective: {objective}")
    value = float(result[objective])
    if not math.isfinite(value):
        raise ValueError(f"Candidate {OBJECTIVES[objective]} must be finite.")
    return value
