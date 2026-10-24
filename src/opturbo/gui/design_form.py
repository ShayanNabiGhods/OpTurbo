"""Focused Tkinter behavior for the OpTurbo application."""

from dataclasses import fields, replace
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..models import GeometrySettings, VariableSpec, default_design_variables
from ..workflows.axisymmetric_2d.geometry.design_import import read_design_snapshot
from .widgets import ScrollableFrame, ToolTip


class DesignFormMixin:
    def _build_design_tab(self) -> None:
        tab = ttk.Panedwindow(self.notebook, orient="horizontal")
        self.notebook.add(tab, text="  Design  ")
        left = ttk.Frame(tab, padding=8)
        right = ttk.Frame(tab, padding=8)
        tab.add(left, weight=2)
        tab.add(right, weight=3)
        ttk.Label(left, text="Duct design", style="Title.TLabel").pack(anchor="w")
        chooser = ttk.Frame(left)
        chooser.pack(fill="x", pady=(4, 6))
        ttk.Label(chooser, text="Design type:").pack(side="left")
        self.design_type_var = tk.StringVar(value=self.config_model.geometry.design_type)
        design_picker = ttk.Combobox(chooser, textvariable=self.design_type_var, state="readonly",
                                     values=("airfoil", "flanged"), width=16)
        design_picker.pack(side="left", padx=8)
        design_picker.bind("<<ComboboxSelected>>", self._switch_design_type)
        ttk.Label(left, text="Only variables used by the selected design are shown. Unticked rows stay fixed.",
                  style="Subtitle.TLabel", wraplength=500).pack(anchor="w", pady=(0, 8))
        self.parsec_scroll = ScrollableFrame(left)
        self.parsec_scroll.pack(fill="both", expand=True)
        self.parsec_body = self.parsec_scroll.body
        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=8)
        ttk.Button(controls, text="Load design…", command=self._load_design_settings).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Update preview", command=self._update_preview_from_fields).pack(side="left")
        ttk.Button(controls, text="Select all", command=lambda: self._select_parsec(True)).pack(side="left", padx=6)
        ttk.Button(controls, text="Clear all", command=lambda: self._select_parsec(False)).pack(side="left")
        views = ttk.Notebook(right)
        views.pack(fill="both", expand=True)
        whole = ttk.Frame(views)
        zoom = ttk.Frame(views)
        views.add(whole, text="Whole domain")
        views.add(zoom, text="Duct detail")
        self.domain_canvas = tk.Canvas(whole, background="white", highlightthickness=0)
        self.duct_canvas = tk.Canvas(zoom, background="white", highlightthickness=0)
        self.domain_canvas.pack(fill="both", expand=True)
        self.duct_canvas.pack(fill="both", expand=True)
        self.domain_canvas.bind("<Configure>", lambda _event: self._draw_design())
        self.duct_canvas.bind("<Configure>", lambda _event: self._draw_design())

    def _make_parsec_rows(self) -> None:
        for child in self.parsec_body.winfo_children():
            child.destroy()
        self.parsec_rows.clear()
        self.variable_controls.clear()
        for column, text in ((0, "Use"), (1, "Parameter"), (2, "Minimum"), (3, "Value"), (4, "Maximum")):
            ttk.Label(self.parsec_body, text=text).grid(row=0, column=column, sticky="w", padx=3)
        for row, spec in enumerate(self.config_model.design_variables, start=1):
            enabled = tk.BooleanVar(value=spec.optimize)
            value = tk.StringVar(value=self._format_user_number(spec.value))
            minimum = tk.StringVar(value=self._format_user_number(spec.minimum))
            maximum = tk.StringVar(value=self._format_user_number(spec.maximum))
            use = ttk.Checkbutton(self.parsec_body, variable=enabled)
            use.grid(row=row, column=0, padx=3, pady=3)
            label = ttk.Label(self.parsec_body, text=spec.label)
            numeric_options = {"validate": "key", "validatecommand": self.numeric_entry_validate}
            value_entry = ttk.Entry(self.parsec_body, textvariable=value, width=11, **numeric_options)
            minimum_entry = ttk.Entry(self.parsec_body, textvariable=minimum, width=11, **numeric_options)
            maximum_entry = ttk.Entry(self.parsec_body, textvariable=maximum, width=11, **numeric_options)
            label.grid(row=row, column=1, sticky="w", padx=3)
            minimum_entry.grid(row=row, column=2, padx=3)
            value_entry.grid(row=row, column=3, padx=3)
            maximum_entry.grid(row=row, column=4, padx=3)
            hint = f"Select to optimize {spec.label.lower()}; otherwise its current value stays fixed."
            ToolTip(use, hint)
            ToolTip(label, hint)
            ToolTip(value_entry, f"Current design value for {spec.label.lower()}.")
            ToolTip(minimum_entry, f"Lowest permitted optimization value for {spec.label.lower()}.")
            ToolTip(maximum_entry, f"Highest permitted optimization value for {spec.label.lower()}.")
            value.trace_add("write", lambda *_args: self.after_idle(self._draw_design))
            self.parsec_rows.append((spec, enabled, value, minimum, maximum))
            self.variable_controls[spec.key] = (label, value_entry, minimum_entry, maximum_entry)
            enabled.trace_add("write", lambda *_args, key=spec.key, flag=enabled:
                              self._set_variable_row_state(key, flag.get()))
            self._set_variable_row_state(spec.key, enabled.get())
        self.parsec_body.columnconfigure(1, weight=1)
        for column in (0, 2, 3, 4):
            self.parsec_body.columnconfigure(column, weight=0)

    def _set_variable_row_state(self, key: str, enabled: bool) -> None:
        """Gray and lock fixed design-variable rows while keeping their checkbox usable."""
        state = "!disabled" if enabled else "disabled"
        for widget in self.variable_controls.get(key, ()):
            widget.state([state])

    def _switch_design_type(self, _event: object | None = None) -> None:
        """Replace the Design-tab choices with those valid for the selected duct."""
        if self.worker and self.worker.is_alive():
            self.design_type_var.set(self.config_model.geometry.design_type)
            return
        selected = self.design_type_var.get()
        current = self.config_model.geometry.design_type
        if selected == current or selected not in {"airfoil", "flanged"}:
            return
        current_rows = []
        for spec, enabled, value, minimum, maximum in self.parsec_rows:
            try:
                current_rows.append(VariableSpec(spec.key, spec.label, float(value.get()),
                                                 float(minimum.get()), float(maximum.get()), enabled.get()))
            except ValueError:
                current_rows.append(spec)
        self.design_variable_sets[current] = current_rows
        next_rows = self.design_variable_sets.get(selected, default_design_variables(selected))
        self.config_model.geometry = replace(self.config_model.geometry, design_type=selected,
                                             duct_reverse=(selected == "airfoil"))
        self.field_vars[("geometry", "design_type")].set(selected)
        self.field_vars[("geometry", "duct_reverse")].set(selected == "airfoil")
        self.config_model.design_variables = next_rows[:]
        self._make_parsec_rows()
        self._draw_design()

    def _load_design_settings(self) -> None:
        """Load a design from a best-result snapshot or geometry-settings JSON."""
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Run active", "Stop the active run before loading a different design.")
            return
        selected_path = filedialog.askopenfilename(
            title="Load design settings",
            filetypes=(("OpTurbo design settings", "*.json"), ("JSON files", "*.json"),
                       ("All files", "*.*")),
        )
        if not selected_path:
            return
        path = Path(selected_path)
        try:
            snapshot = read_design_snapshot(path, self.config_model.geometry.design_type)
            geometry_data = snapshot.geometry
            variable_values = snapshot.variables
            design_type = snapshot.design_type

            if design_type != self.config_model.geometry.design_type:
                self.design_type_var.set(design_type)
                self._switch_design_type()

            geometry_updates = {}
            for item in fields(GeometrySettings):
                if item.name == "design_type":
                    continue
                raw_value = variable_values.get(f"geometry.{item.name}", geometry_data.get(item.name))
                if raw_value is None:
                    continue
                if isinstance(getattr(self.config_model.geometry, item.name), bool):
                    raw_value = (raw_value if isinstance(raw_value, bool)
                                 else str(raw_value).strip().lower() in {"true", "1", "yes"})
                elif isinstance(getattr(self.config_model.geometry, item.name), int):
                    raw_value = int(raw_value)
                elif isinstance(getattr(self.config_model.geometry, item.name), float):
                    raw_value = float(raw_value)
                    raw_value = float(self._format_user_number(raw_value))
                geometry_updates[item.name] = raw_value
                self.field_vars[("geometry", item.name)].set(raw_value)
            geometry_updates["design_type"] = design_type
            self.config_model.geometry = replace(self.config_model.geometry, **geometry_updates)

            loaded_variables = []
            for spec in self.config_model.design_variables:
                raw_value = variable_values.get(spec.key)
                if raw_value is None:
                    loaded_variables.append(spec)
                    continue
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError(f"{spec.label} must be a finite number.")
                loaded_variables.append(replace(spec, value=value,
                                                minimum=min(spec.minimum, value),
                                                maximum=max(spec.maximum, value)))
            self.config_model.design_variables = loaded_variables
            self.design_variable_sets[design_type] = loaded_variables[:]
            self._make_parsec_rows()
            self._draw_design()
            self.status_var.set(f"Design loaded from {path.name}")
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as error:
            messagebox.showerror("Cannot load design", str(error))

    def _select_parsec(self, selected: bool) -> None:
        for _, enabled, *_ in self.parsec_rows:
            enabled.set(selected)
