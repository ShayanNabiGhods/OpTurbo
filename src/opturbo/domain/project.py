"""Serializable project configuration and backward-compatible JSON reader."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .accessibility import AccessibilitySettings
from .cfd import CfdSettings
from .design import GeometrySettings, VariableSpec, default_design_variables
from .mesh import MeshSettings
from .optimization import GaSettings
from .tools import ToolPaths


@dataclass
class ProjectConfig:
    """Complete serializable application configuration."""

    project_name: str = "Untitled optimization"
    save_dir: str = ""
    workflow_id: str = "axisymmetric_2d"
    workflow_settings: dict[str, Any] = field(default_factory=dict)
    tools: ToolPaths = field(default_factory=ToolPaths)
    geometry: GeometrySettings = field(default_factory=GeometrySettings)
    mesh: MeshSettings = field(default_factory=MeshSettings)
    cfd: CfdSettings = field(default_factory=CfdSettings)
    ga: GaSettings = field(default_factory=GaSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    design_variables: list[VariableSpec] = field(
        default_factory=lambda: default_design_variables("flanged"))

    def to_dict(self) -> dict[str, Any]:
        """Convert the configuration into JSON-compatible values."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Rebuild a configuration loaded from JSON."""
        workflow_id = data.get("workflow_id", "axisymmetric_2d")
        workflow_settings = data.get("workflow_settings", {})
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("Project workflow_id must be a non-empty string.")
        if not isinstance(workflow_settings, dict):
            raise ValueError("Project workflow_settings must be a JSON object.")
        geometry_data = dict(data.get("geometry", {}))
        # Saved projects created before duct-family selection were airfoil-based.
        if "design_type" not in geometry_data:
            geometry_data["design_type"] = "airfoil"
        geometry = GeometrySettings(**geometry_data)
        raw_variables = data.get("design_variables", data.get("parsec_variables", []))
        variables = [VariableSpec(**item) for item in raw_variables]
        defaults = default_design_variables(geometry.design_type)
        allowed = {item.key for item in defaults}
        variables = [item for item in variables if item.key in allowed]
        existing = {item.key for item in variables}
        for default in defaults:
            if default.key not in existing:
                if default.key == "geometry.duct_angle_deg":
                    default.value = geometry.duct_angle_deg
                elif default.key == "geometry.duct_chord" and "duct_chord" in geometry_data:
                    default.value = geometry.duct_chord
                elif default.key == "geometry.duct_thickness" and "duct_thickness" in geometry_data:
                    default.value = geometry.duct_thickness
                elif default.key == "geometry.duct_flange_length" and "duct_flange_length" in geometry_data:
                    default.value = geometry.duct_flange_length
                elif default.key == "geometry.duct_flange_angle_deg" and "duct_flange_angle_deg" in geometry_data:
                    default.value = geometry.duct_flange_angle_deg
                variables.insert(0 if default.key.startswith("geometry.") else len(variables), default)
        cfd_data = dict(data.get("cfd", {}))
        # Older projects may contain this retired setting; never forward it.
        cfd_data.pop("gradient_scheme", None)
        return cls(
            project_name=data.get("project_name", "Untitled optimization"),
            save_dir=data.get("save_dir", ""),
            workflow_id=workflow_id,
            workflow_settings=workflow_settings,
            tools=ToolPaths(**data.get("tools", {})),
            geometry=geometry,
            mesh=MeshSettings(**data.get("mesh", {})),
            cfd=CfdSettings(**cfd_data),
            ga=GaSettings(**data.get("ga", {})),
            accessibility=AccessibilitySettings(**data.get("accessibility", {})),
            design_variables=variables or defaults,
        )

    @property
    def save_path(self) -> Path | None:
        """Return the selected project path, if one has been chosen."""
        return Path(self.save_dir) if self.save_dir else None
