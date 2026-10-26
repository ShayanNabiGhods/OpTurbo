"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields
import tkinter as tk
from tkinter import ttk

from ..objectives import OBJECTIVES
from .constants import CFD_CHOICE_VALUES, CPU_CORE_CHOICES, FIELD_HELP, LABELS
from .widgets import ToolTip


class SettingsFormMixin:
    def _add_dataclass_form(self, parent: ttk.Frame, section: str, cls: type,
                            browse_paths: bool = False, exclude: set[str] | None = None,
                            two_columns: bool = False,
                            include: set[str] | None = None,
                            inline_help: bool = True) -> None:
        """Create labeled entries for every field in a settings dataclass."""
        row = 0
        container = parent
        all_fields = list(fields(cls))
        for index, item in enumerate(all_fields):
            if two_columns and index in (0, (len(all_fields) + 1) // 2):
                column = 0 if index == 0 else 1
                parent = ttk.Frame(container, padding=8)
                parent.grid(row=0, column=column, sticky="new")
                container.columnconfigure(column, weight=1, uniform="settings")
                row = 0
            key = (section, item.name)
            label = LABELS.get(item.name, item.name.replace("_", " ").title())
            default = getattr(cls(), item.name)
            variable = self.field_vars.get(key)
            if variable is None:
                variable = tk.BooleanVar() if isinstance(default, bool) else tk.StringVar()
                self.field_vars[key] = variable
            if exclude and item.name in exclude:
                continue
            if include is not None and item.name not in include:
                continue
            if section == "cfd" and item.name == "tip_loss_model":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=("prandtl", "bontempo2025"))
            elif section == "ga" and item.name == "objective":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=tuple(OBJECTIVES))
            elif section == "cfd" and item.name in CFD_CHOICE_VALUES:
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=CFD_CHOICE_VALUES[item.name])
            elif section == "mesh" and item.name == "method":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=("Default (ANSYS automatic)", "Quad", "Tri", "MultiZone"))
            elif section == "mesh" and item.name == "cpu_cores":
                widget = ttk.Combobox(parent, textvariable=variable, state="readonly",
                                      values=CPU_CORE_CHOICES)
            elif isinstance(default, bool):
                widget = ttk.Checkbutton(parent, variable=variable)
            else:
                entry_options = {"validate": "key", "validatecommand": self.numeric_entry_validate} \
                    if isinstance(default, (int, float)) and not isinstance(default, bool) else {}
                widget = ttk.Entry(parent, textvariable=variable, width=24, **entry_options)
            if section == "cfd" and item.name in {"bontempo_g_a", "bontempo_g_b", "bontempo_g_c"}:
                self.bontempo_controls.append(widget)
            if section == "cfd" and item.name == "previous_source_weight":
                self.source_weight_control = widget
            label_widget = ttk.Label(parent, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=5, pady=5)
            widget.grid(row=row, column=1, sticky="ew" if browse_paths else "w", padx=5, pady=5)
            if not hasattr(self, "setting_controls"):
                self.setting_controls = {}
            self.setting_controls[key] = (label_widget, widget)
            if section == "mesh" and item.name in {"inflation_layers", "inflation_max_thickness_cm"}:
                self.inflation_dependent_controls.extend((label_widget, widget))
            help_text = FIELD_HELP.get(item.name, f"Controls {label.lower()}.")
            if inline_help:
                ttk.Label(parent, text=help_text, style="Subtitle.TLabel", wraplength=360,
                          justify="left").grid(row=row + 1, column=1, columnspan=2,
                                               sticky="w", padx=5, pady=(0, 5))
            ToolTip(label_widget, help_text)
            ToolTip(widget, help_text)
            if section == "tools" and item.name == "handoff_dir":
                widget.configure(state="readonly")
                ttk.Label(parent, text="Protected", foreground="#a34a2a").grid(row=row, column=2, padx=4)
            elif browse_paths:
                ttk.Button(parent, text="Browse…", command=lambda var=variable: self._browse_tool(var)).grid(row=row, column=2, padx=4)
            row += 2 if inline_help else 1
        parent.columnconfigure(1, weight=1)

    def _place_setting_groups(self, parent: ttk.Frame, section: str, cls: type,
                              groups: tuple[tuple[str, tuple[str, ...]], ...],
                              exclude: set[str] | None = None) -> tuple[ttk.Frame, ttk.Frame]:
        """Stack related settings groups in two independent compact columns."""
        columns = (ttk.Frame(parent), ttk.Frame(parent))
        for column, frame in enumerate(columns):
            frame.grid(row=0, column=column, sticky="new")
            parent.columnconfigure(column, weight=1, uniform=f"{section}_groups")
        for index, (title, names) in enumerate(groups):
            group = ttk.LabelFrame(columns[index % 2], text=title, padding=8)
            if section == "geometry" and title == "Hub and duct placement":
                self.hub_duct_settings_group = group
            group.pack(fill="x", padx=7, pady=6)
            self._add_dataclass_form(group, section, cls, exclude=exclude,
                                     include=set(names), inline_help=False)
        return columns
