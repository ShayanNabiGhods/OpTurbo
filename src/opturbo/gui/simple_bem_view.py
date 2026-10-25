"""Standalone BEM sweep panel that does not invoke the CFD pipeline."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..paths import RESOURCES_ROOT
from ..simple_bem import run_tsr_sweep
from ..workflows.axisymmetric_2d.cfd.models import Flow, Turbine
from ..workflows.axisymmetric_2d.cfd.resources import load_airfoil, load_blade


class SimpleBemViewMixin:
    """Build and operate the CFD-free BEM calculation panel."""

    def _build_simple_bem_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="  Simple BEM  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        ttk.Label(
            tab,
            text=("Calculate rotor performance directly from the current flow and rotor settings. "
                  "This panel uses the bundled NTNU blade and S826 polars; it does not run CFD "
                  "or create a duct/domain model."),
            wraplength=1000,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        controls = ttk.LabelFrame(tab, text="TSR sweep", padding=10)
        controls.grid(row=1, column=0, sticky="ew")
        self.simple_bem_min_var = tk.StringVar(value="4")
        self.simple_bem_max_var = tk.StringVar(value="8")
        self.simple_bem_step_var = tk.StringVar(value="0.5")
        self.simple_bem_tip_loss_var = tk.StringVar(value="prandtl")
        for column, (label, variable) in enumerate((
            ("Minimum TSR", self.simple_bem_min_var),
            ("Maximum TSR", self.simple_bem_max_var),
            ("TSR interval", self.simple_bem_step_var),
        )):
            ttk.Label(controls, text=label).grid(row=0, column=column * 2, sticky="w", padx=(0, 5))
            ttk.Entry(controls, textvariable=variable, width=10,
                      validate="key", validatecommand=self.numeric_entry_validate).grid(
                          row=0, column=column * 2 + 1, sticky="w", padx=(0, 14))
        ttk.Label(controls, text="Tip-loss method").grid(row=0, column=6, sticky="w", padx=(0, 5))
        ttk.Combobox(controls, textvariable=self.simple_bem_tip_loss_var,
                     values=("prandtl", "bontempo2025"), state="readonly", width=16).grid(
                         row=0, column=7, sticky="w", padx=(0, 14))
        ttk.Button(controls, text="Run BEM sweep", command=self._run_simple_bem_sweep).grid(
            row=0, column=8, sticky="e")
        controls.columnconfigure(8, weight=1)

        self.simple_bem_status_var = tk.StringVar(value="Ready. The sweep uses the current Workflow Settings turbine inputs.")
        ttk.Label(tab, textvariable=self.simple_bem_status_var, style="Subtitle.TLabel").grid(
            row=2, column=0, sticky="nw", pady=(8, 4))
        results_frame = ttk.LabelFrame(tab, text="Results", padding=6)
        results_frame.grid(row=3, column=0, sticky="nsew")
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        columns = ("tsr", "omega", "power", "cp", "ct", "convergence")
        self.simple_bem_table = ttk.Treeview(results_frame, columns=columns, show="headings", height=15)
        headings = (
            ("tsr", "TSR (-)", 100),
            ("omega", "Angular speed (rad/s)", 175),
            ("power", "Power (W)", 150),
            ("cp", "Cp (-)", 120),
            ("ct", "Ct (-)", 120),
            ("convergence", "Induction stations converged", 205),
        )
        for name, title, width in headings:
            self.simple_bem_table.heading(name, text=title)
            self.simple_bem_table.column(name, width=width, anchor="center")
        yscroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.simple_bem_table.yview)
        self.simple_bem_table.configure(yscrollcommand=yscroll.set)
        self.simple_bem_table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

    def _run_simple_bem_sweep(self) -> None:
        """Run the inexpensive rotor-only solver from live workflow settings."""
        try:
            def number(name: str) -> float:
                return float(self.field_vars[("cfd", name)].get())

            flow = Flow(number("flow_speed_m_s"), number("density_kg_m3"), number("viscosity_pa_s"))
            rotor_radius = number("rotor_radius_m")
            hub_radius = number("hub_radius_m")
            raw_blades = float(self.field_vars[("cfd", "blades")].get())
            if not raw_blades.is_integer():
                raise ValueError("Blade count must be a whole number.")
            blades = int(raw_blades)
            pitch = number("pitch_deg")
            tip_model = self.simple_bem_tip_loss_var.get()
            raw_stations = number("stations")
            if not raw_stations.is_integer() or raw_stations < 2:
                raise ValueError("BEM radial stations must be a whole number of at least two.")
            turbine = Turbine(
                radius=rotor_radius,
                hub_radius=hub_radius,
                blades=blades,
                omega=number("omega_rad_s"),
                pitch=pitch,
                tip_loss_model=tip_model,
                bontempo_g_a=number("bontempo_g_a"),
                bontempo_g_b=number("bontempo_g_b"),
                bontempo_g_c=number("bontempo_g_c"),
            )
            resources = RESOURCES_ROOT / "cfd_tables"
            base_radius = 0.45
            blade = load_blade(resources, stations=int(raw_stations))
            scale = rotor_radius / base_radius
            blade.radius = [value * scale for value in blade.radius]
            blade.chord = [value * scale for value in blade.chord]
            blade.dr = [value * scale for value in blade.dr]
            airfoil = load_airfoil(resources)
            results = run_tsr_sweep(
                flow, turbine, blade, airfoil,
                float(self.simple_bem_min_var.get()),
                float(self.simple_bem_max_var.get()),
                float(self.simple_bem_step_var.get()),
            )
        except (KeyError, TypeError, ValueError, OSError) as error:
            messagebox.showerror("Simple BEM", str(error))
            return

        for item in self.simple_bem_table.get_children():
            self.simple_bem_table.delete(item)
        for result in results:
            performance = result.performance
            self.simple_bem_table.insert("", "end", values=(
                f"{result.tip_speed_ratio:.3g}", f"{result.omega_rad_s:.4g}",
                f"{performance.power:.6g}", f"{performance.cp:.6g}",
                f"{performance.ct:.6g}",
                f"{result.converged_stations}/{result.station_count}",
            ))
        self.simple_bem_status_var.set(
            f"Completed {len(results)} CFD-free BEM operating points using {tip_model} tip-loss correction."
        )
