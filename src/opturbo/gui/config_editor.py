"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields, replace

from ..models import AccessibilitySettings, CfdSettings, GaSettings, GeometrySettings, MeshSettings, ProjectConfig, ToolPaths, VariableSpec
from ..objectives import OBJECTIVES
from ..workflows.axisymmetric_2d.geometry.parameters import (
    nested_parameters,
    validate_lower_profile,
    validate_profile,
)
from ..domain.validation import validate_project_settings


class ConfigEditorMixin:
    def _read_model_from_fields(self) -> ProjectConfig:
        def build(section: str, cls: type):
            values = {}
            instance = cls()
            for item in fields(cls):
                raw = self.field_vars[(section, item.name)].get()
                default = getattr(instance, item.name)
                if section == "mesh" and item.name == "cpu_cores":
                    values[item.name] = None if raw == "Program Controlled" else int(raw)
                elif isinstance(default, bool):
                    values[item.name] = bool(raw)
                elif isinstance(default, int):
                    values[item.name] = int(raw)
                elif isinstance(default, float):
                    values[item.name] = float(raw)
                elif section == "mesh" and item.name == "method":
                    values[item.name] = "Default" if raw == "Default (ANSYS automatic)" else str(raw)
                else:
                    values[item.name] = str(raw)
            return cls(**values)

        variables = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            parsed = VariableSpec(spec.key, spec.label, float(value.get()), float(minimum.get()),
                                  float(maximum.get()), enabled.get())
            if parsed.minimum >= parsed.maximum:
                raise ValueError(f"{parsed.label}: minimum must be less than maximum.")
            if not parsed.minimum <= parsed.value <= parsed.maximum:
                raise ValueError(f"{parsed.label}: current value must be inside its bounds.")
            variables.append(parsed)
        model = ProjectConfig(
            project_name=self.project_name_var.get().strip() or "Untitled optimization",
            save_dir=self.save_dir_var.get(), tools=build("tools", ToolPaths),
            workflow_id=self.workflow_id_var.get(),
            workflow_settings=dict(self.config_model.workflow_settings),
            geometry=build("geometry", GeometrySettings), mesh=build("mesh", MeshSettings),
            cfd=build("cfd", CfdSettings), ga=build("ga", GaSettings),
            accessibility=AccessibilitySettings(theme=self.theme_var.get(), text_scale=int(self.text_scale_var.get()),
                                                high_contrast=self.high_contrast_var.get(), accent_color=self.accent_var.get(),
                                                candidate_marker_size=int(self.candidate_marker_size_var.get()),
                                                outer_marker_size=int(self.outer_marker_size_var.get()),
                                                table_row_spacing=int(self.table_row_spacing_var.get())), design_variables=variables,
        )
        geometry_values = {
            item.key.split(".", 1)[1]: item.value
            for item in variables if item.key.startswith("geometry.")
        }
        model.geometry = replace(model.geometry, **geometry_values)
        if model.geometry.design_type == "flanged":
            validate_lower_profile(nested_parameters(variables))
        else:
            validate_profile(nested_parameters(variables))
        self._validate_positive_settings(model)
        if model.ga.objective not in OBJECTIVES:
            raise ValueError("Choose Cp, Ct, normalized Cp, or normalized Ct as the optimization criterion.")
        return model

    @staticmethod
    def _validate_positive_settings(config: ProjectConfig) -> None:
        """Compatibility wrapper for shared engineering input validation."""
        validate_project_settings(config)
