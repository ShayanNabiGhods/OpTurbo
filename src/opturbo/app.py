"""Public Tkinter application entry point and compatibility exports."""

import tkinter as tk
from tkinter import ttk

from .gui.configuration import saved_configuration_matches
from .gui.constants import (
    APP_ROOT, CFD_CHOICE_VALUES, CPU_CORE_CHOICES, FIELD_HELP, LABELS,
    MESH_STUDY_SIZE_FIELDS, TURBULENCE_EQUATIONS, TURBULENCE_FIELDS,
)
from .gui.widgets import LinePlot, ScrollableFrame, ToolTip
from .gui.window import OpTurboWindow


class OpTurboApp(OpTurboWindow):
    """Compatibility name for the composed desktop application."""

    def _refresh_turbulence_controls(self, *_args: object) -> None:
        """Show active-model equations while retaining values for hidden models."""
        panel = self.turbulence_panel
        for child in panel.winfo_children():
            child.destroy()
        ttk.Label(panel, text="Viscous turbulence model").grid(row=0, column=0, sticky="w", padx=5)
        model = self.field_vars[("cfd", "viscous_model")]
        ttk.Combobox(panel, textvariable=model, values=CFD_CHOICE_VALUES["viscous_model"],
                     state="readonly", width=24).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(panel, text="Only active equations are shown. Switching models preserves your settings.",
                  style="Subtitle.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        for column, equation in enumerate(TURBULENCE_EQUATIONS.get(model.get(), ())):
            group = ttk.LabelFrame(panel, text=equation, padding=8)
            group.grid(row=2, column=column, sticky="new", padx=5)
            for row, name in enumerate((f"residual_{equation}", f"{equation}_scheme")):
                ttk.Label(group, text=LABELS[name]).grid(row=row * 3, column=0, sticky="w")
                variable = self.field_vars[("cfd", name)]
                if name in CFD_CHOICE_VALUES:
                    control = ttk.Combobox(group, textvariable=variable, values=CFD_CHOICE_VALUES[name],
                                            state="readonly", width=24)
                else:
                    control = ttk.Entry(group, textvariable=variable, width=24,
                                        validate="key", validatecommand=self.numeric_entry_validate)
                control.grid(row=row * 3 + 1, column=0, sticky="w", pady=3)
                ttk.Label(group, text=FIELD_HELP[name], style="Subtitle.TLabel", wraplength=330,
                          justify="left").grid(row=row * 3 + 2, column=0, sticky="w", pady=(0, 8))
                ToolTip(control, FIELD_HELP[name])
        for column in (0, 1):
            panel.columnconfigure(column, weight=1, uniform="turbulence")


def main() -> None:
    """Create and run the OpTurbo desktop application."""
    OpTurboApp().mainloop()
