"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields
from tkinter import ttk

from ..models import CfdSettings, GeometrySettings, MeshSettings
from .widgets import ScrollableFrame


class WorkflowSettingsMixin:
    def _build_workflow_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.workflow_tab = tab
        self.notebook.add(tab, text="  Workflow Settings  ")
        pages = ttk.Notebook(tab)
        self.workflow_pages = pages
        pages.pack(fill="both", expand=True)
        for title, section, cls in (("Geometry", "geometry", GeometrySettings),
                                    ("Meshing", "mesh", MeshSettings),
                                    ("CFD / BEM", "cfd", CfdSettings)):
            page = ScrollableFrame(pages)
            body = page.body
            pages.add(page, text=title)
            if section == "mesh":
                self.mesh_settings_page = page
            # Initialize a persistent variable for every setting before placing
            # fields into separate groups (including currently hidden equations).
            self._add_dataclass_form(body, section, cls,
                                     exclude={item.name for item in fields(cls)})
            if section == "geometry":
                groups = (
                    ("Outer domain", ("domain_length", "domain_height", "domain_origin_x", "domain_origin_r")),
                    ("Resolution region", ("resolution_length", "resolution_inlet_radius", "resolution_origin_x", "resolution_origin_r")),
                    ("Actuator disk", ("actuator_radial_span", "actuator_thickness", "actuator_origin_x")),
                    ("Hub and duct placement", ("hub_length", "hub_radius", "hub_origin_x", "hub_origin_r", "duct_origin_x", "duct_origin_r", "duct_points")),
                )
                self._place_setting_groups(body, section, cls, groups, exclude={
                    "design_type", "duct_angle_deg", "duct_chord", "duct_thickness",
                    "duct_flange_length", "duct_flange_angle_deg"})
            elif section == "mesh":
                groups = (
                    ("Global mesh controls", ("global_size_cm", "growth_rate", "cpu_cores", "method", "curvature_angle_deg")),
                    ("Local sizing", ("resolution_size_cm", "duct_size_cm", "hub_size_cm")),
                    ("Inflation layers", ("inflation_enabled", "inflation_layers", "inflation_max_thickness_cm")),
                )
                self._place_setting_groups(body, section, cls, groups)
                self.field_vars[("mesh", "inflation_enabled")].trace_add(
                    "write", self._refresh_inflation_controls)
                self._refresh_inflation_controls()
            else:
                groups = (
                    ("Flow and rotor", ("flow_speed_m_s", "density_kg_m3", "viscosity_pa_s", "rotor_radius_m", "hub_radius_m", "blades", "omega_rad_s", "pitch_deg")),
                    ("BEM correction", ("stations", "tip_loss_model")),
                    ("Fluent / BEM coupling", ("max_outer_iterations", "fluent_iterations", "tolerance", "relaxation", "processors", "keep_iteration_data", "source_initialization", "previous_source_weight")),
                    ("Fluent discretization", ("pressure_scheme", "momentum_scheme", "swirl_scheme", "pressure_velocity_coupling")),
                    ("General residual criteria", ("residual_continuity", "residual_x_velocity", "residual_y_velocity", "residual_swirl")),
                )
                columns = self._place_setting_groups(body, section, cls, groups)
                self.turbulence_panel = ttk.LabelFrame(
                    columns[1], text="Turbulence model and equation residuals", padding=10)
                self.turbulence_panel.pack(fill="x", padx=7, pady=6)
                self.field_vars[("cfd", "viscous_model")].trace_add("write", self._refresh_turbulence_controls)
                self.field_vars[("cfd", "source_initialization")].trace_add("write", self._refresh_source_weight_control)
                self._refresh_source_weight_control()
                self._refresh_turbulence_controls()
                self.bontempo_panel = ttk.LabelFrame(
                    columns[1], text="Bontempo g coefficients", padding=8)
                self.bontempo_panel.pack(fill="x", padx=7, pady=6)
                self._add_dataclass_form(self.bontempo_panel, section, cls,
                                         include={"bontempo_g_a", "bontempo_g_b", "bontempo_g_c"},
                                         inline_help=False)
                self.field_vars[("cfd", "tip_loss_model")].trace_add("write", self._refresh_bontempo_controls)
                self._refresh_bontempo_controls()

    def _refresh_bontempo_controls(self, *_args: object) -> None:
        """Gray empirical g coefficients unless the Bontempo correction is selected."""
        enabled = self.field_vars[("cfd", "tip_loss_model")].get() == "bontempo2025"
        for control in self.bontempo_controls:
            control.configure(state="normal" if enabled else "disabled")

    def _refresh_source_weight_control(self, *_args: object) -> None:
        """Enable previous-source weighting only in warm-start mode."""
        control = getattr(self, "source_weight_control", None)
        if control is not None:
            enabled = self.field_vars[("cfd", "source_initialization")].get() == "previous_candidate"
            control.configure(state="normal" if enabled else "disabled")

    def _refresh_inflation_controls(self, *_args: object) -> None:
        """Gray layer-count and thickness controls when inflation is disabled."""
        variable = self.field_vars.get(("mesh", "inflation_enabled"))
        if variable is None:
            return
        state = "!disabled" if variable.get() else "disabled"
        for control in self.inflation_dependent_controls:
            control.state([state])
