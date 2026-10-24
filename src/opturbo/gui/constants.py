"""Compatibility exports for GUI labels, choices, and application paths."""

from ..paths import APPLICATION_ROOT as APP_ROOT
from .choices import (
    CFD_CHOICE_VALUES, CPU_CORE_CHOICES, MESH_STUDY_SIZE_FIELDS,
    TURBULENCE_EQUATIONS, TURBULENCE_FIELDS,
)
from .labels import FIELD_HELP, LABELS

__all__ = [
    "APP_ROOT", "CFD_CHOICE_VALUES", "CPU_CORE_CHOICES", "FIELD_HELP",
    "LABELS", "MESH_STUDY_SIZE_FIELDS", "TURBULENCE_EQUATIONS",
    "TURBULENCE_FIELDS",
]
