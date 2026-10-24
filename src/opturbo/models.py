"""Backward-compatible public model imports.

New code can import models from the focused :mod:`opturbo.domain` modules.
"""

from .domain.accessibility import AccessibilitySettings
from .domain.cfd import CfdSettings
from .domain.design import (
    GeometrySettings,
    VariableSpec,
    default_airfoil_variables,
    default_design_variables,
    default_flanged_variables,
    default_parsec_variables,
)
from .domain.mesh import MeshSettings
from .domain.optimization import GaSettings
from .domain.project import ProjectConfig
from .domain.tools import ToolPaths

__all__ = [
    "AccessibilitySettings", "CfdSettings", "GaSettings", "GeometrySettings",
    "MeshSettings", "ProjectConfig", "ToolPaths", "VariableSpec",
    "default_airfoil_variables", "default_design_variables",
    "default_flanged_variables", "default_parsec_variables",
]
