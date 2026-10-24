"""Backward-compatible exports for the axisymmetric CFD package."""

from ..workflows.axisymmetric_2d.cfd import (
    Airfoil, Blade, Flow, Performance, Results, Sources, Turbine,
    load_airfoil, load_blade, load_setup, performance, solve, sources_from,
)

__all__ = [
    "Airfoil", "Blade", "Flow", "Performance", "Results", "Sources",
    "Turbine", "load_airfoil", "load_blade", "load_setup", "performance",
    "solve", "sources_from",
]
