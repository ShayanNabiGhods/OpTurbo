"""Edit or import the blade and airfoil tables used by both CFD workflows."""

import math
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..paths import APPLICATION_ROOT
from ..pipeline.aerodynamic_tables import (
    CFD_TABLE_FILES,
    load_cfd_tables,
    read_numeric_csv,
    save_cfd_tables,
    validate_cfd_table_import,
    workflow_cfd_tables_directory,
)


_TABLE_FORMATS = {
    "ntnu_geometry.csv": (
        ("Radius (m)", "Chord (m)", "Twist (deg)"),
        "One blade section per row; three numeric columns: radius (m), chord (m), and twist (deg). "
        "Use at least two rows in hub-to-tip order. The row count may be any number of sections.",
    ),
    "s826_alpha.csv": (
        ("Angle (deg)",),
        "One angle-of-attack value in degrees per row, strictly increasing. No header row.",
    ),
    "s826_re.csv": (
        ("Re 1", "Re 2", "Re 3", "…"),
        "One row containing at least two positive, strictly increasing Reynolds numbers. "
        "Each polar table column must match one value here.",
    ),
    "s826_cl.csv": (
        ("Re 1", "Re 2", "Re 3", "…"),
        "Lift-coefficient matrix: one row per s826_alpha.csv angle and one column per s826_re.csv value. "
        "Values are unitless. Do not include row or column labels.",
    ),
    "s826_cd.csv": (
        ("Re 1", "Re 2", "Re 3", "…"),
        "Drag-coefficient matrix: same dimensions and row/column order as s826_cl.csv. "
        "Values are unitless and must be zero or positive. Do not include labels.",
    ),
}


class AerodynamicDataViewMixin:
    """Provide a shared workflow-aware editor for the packaged BEM CSV files."""

    def _build_aerodynamic_data_tab(self) -> None:
        """Build the CSV table editor and show the required data layout."""
        tab = ttk.Frame(self.notebook, padding=12)
        self.cfd_tables_tab = tab
        self.notebook.add(tab, text="  Aerodynamic Data  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        ttk.Label(
            tab,
            text=("Edit the blade sections and airfoil polar tables used by both CFD/BEM workflows. "
                  "Changes are staged until Save tables is pressed. Each workflow keeps its own copy."),
            wraplength=1080,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(toolbar, text="Table").pack(side="left", padx=(0, 6))
        self.cfd_table_name_var = tk.StringVar(value=CFD_TABLE_FILES[0])
        self.cfd_table_selector = ttk.Combobox(
            toolbar, textvariable=self.cfd_table_name_var, values=CFD_TABLE_FILES,
            state="readonly", width=22,
        )
        self.cfd_table_selector.pack(side="left", padx=(0, 12))
        self.cfd_table_selector.bind("<<ComboboxSelected>>", self._on_cfd_table_selected)
        ttk.Button(toolbar, text="Import selected CSV…", command=self._import_cfd_table).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Save tables", command=self._save_cfd_tables).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Discard edits", command=self._discard_cfd_table_edits).pack(side="left", padx=4)

        self.cfd_table_format_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.cfd_table_format_var, style="Subtitle.TLabel",
                  wraplength=1080, justify="left").grid(row=2, column=0, sticky="new", pady=(0, 8))
        grid_frame = ttk.Frame(tab)
        grid_frame.grid(row=3, column=0, sticky="nsew")
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.rowconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        self.cfd_table_tree = ttk.Treeview(grid_frame, show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.cfd_table_tree.yview)
        xscroll = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.cfd_table_tree.xview)
        self.cfd_table_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.cfd_table_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.cfd_table_tree.bind("<Double-1>", self._begin_cfd_table_cell_edit)
        self.cfd_table_status_var = tk.StringVar(value="Loading workflow tables…")
        ttk.Label(tab, textvariable=self.cfd_table_status_var, style="Subtitle.TLabel").grid(
            row=4, column=0, sticky="w", pady=(8, 0))
        self._cfd_tables_workflow_id: str | None = None
        self.cfd_table_data: dict[str, list[list[float]]] = {}
        self.cfd_table_dirty: set[str] = set()
        self._cfd_table_editor: ttk.Entry | None = None
        self._cfd_table_editor_filename: str | None = None
        self._cfd_table_editor_commit: Callable[[], bool] | None = None
        self.notebook.bind("<<NotebookTabChanged>>", self._on_cfd_tables_tab_selected, add="+")
        self._load_cfd_tables_for_workflow()

    def _cfd_tables_directory(self, workflow_id: str | None = None) -> Path:
        """Return the active workflow's independent aerodynamic table folder."""
        selected_id = workflow_id or self._cfd_tables_workflow_id or self.workflow_id_var.get()
        return workflow_cfd_tables_directory(selected_id, APPLICATION_ROOT)

    def _load_cfd_tables_for_workflow(self, workflow_id: str | None = None) -> None:
        """Read the five source tables from the selected or explicitly named workflow."""
        selected_id = workflow_id or self.workflow_id_var.get()
        self.cfd_table_data, load_errors = load_cfd_tables(self._cfd_tables_directory(selected_id))
        self.cfd_table_dirty.clear()
        self._cfd_tables_workflow_id = selected_id
        self._render_cfd_table()
        status = "Tables loaded. Double-click a value to edit it."
        if load_errors:
            status = "Some saved files need correction or replacement: " + " | ".join(load_errors)
        self._set_cfd_table_status(status)

    def _set_cfd_table_status(self, message: str) -> None:
        """Show the save state and active workflow in the editor."""
        dirty = "Unsaved edits: " + ", ".join(sorted(self.cfd_table_dirty)) if self.cfd_table_dirty else "No unsaved edits"
        workflow = self._cfd_tables_workflow_id or self.workflow_id_var.get()
        self.cfd_table_status_var.set(f"Workflow: {workflow}  |  {dirty}  |  {message}")

    def _render_cfd_table(self, _event: tk.Event | None = None) -> None:
        """Render the selected CSV rows and their column descriptions."""
        if not hasattr(self, "cfd_table_tree") or not self.cfd_table_data:
            return
        filename = self.cfd_table_name_var.get()
        rows = self.cfd_table_data[filename]
        expected, description = _TABLE_FORMATS[filename]
        self.cfd_table_format_var.set(f"Format: {description}")
        column_count = max((len(row) for row in rows), default=1)
        columns = tuple(f"column_{index}" for index in range(column_count))
        self.cfd_table_tree.configure(columns=columns)
        for index, column in enumerate(columns):
            title = expected[index] if index < len(expected) else f"Value {index + 1}"
            self.cfd_table_tree.heading(column, text=title)
            self.cfd_table_tree.column(column, width=140, minwidth=85, anchor="center", stretch=True)
        self.cfd_table_tree.delete(*self.cfd_table_tree.get_children())
        for row_index, row in enumerate(rows):
            values = [format(value, ".10g") for value in row]
            values.extend("" for _ in range(column_count - len(values)))
            self.cfd_table_tree.insert("", "end", iid=str(row_index), values=values)
        self._set_cfd_table_status("Double-click a value to edit it.")

    def _begin_cfd_table_cell_edit(self, event: tk.Event) -> None:
        """Place a small entry over the clicked cell and stage its numeric value."""
        row_id = self.cfd_table_tree.identify_row(event.y)
        column_id = self.cfd_table_tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        bounds = self.cfd_table_tree.bbox(row_id, column_id)
        if not bounds:
            return
        if self._cfd_table_editor_commit and not self._cfd_table_editor_commit():
            return
        if self._cfd_table_editor is not None:
            self._cfd_table_editor.destroy()
        filename = self.cfd_table_name_var.get()
        x, y, width, height = bounds
        value = self.cfd_table_tree.set(row_id, column_id)
        editor = ttk.Entry(self.cfd_table_tree)
        editor.insert(0, value)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        self._cfd_table_editor = editor

        def commit(_event: tk.Event | None = None) -> bool:
            if self._cfd_table_editor is not editor:
                return True
            try:
                number = float(editor.get().strip())
                if not math.isfinite(number):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid table value", "Enter a finite numeric value.")
                editor.focus_set()
                return False
            row_index = int(row_id)
            column_index = int(column_id[1:]) - 1
            self.cfd_table_data[filename][row_index][column_index] = number
            self.cfd_table_dirty.add(filename)
            self._cfd_table_editor = None
            self._cfd_table_editor_filename = None
            self._cfd_table_editor_commit = None
            editor.destroy()
            self._render_cfd_table()
            return True

        self._cfd_table_editor_filename = filename
        self._cfd_table_editor_commit = lambda: commit()
        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda _event: self._cancel_cfd_table_cell_edit(editor))
        editor.focus_set()

    def _cancel_cfd_table_cell_edit(self, editor: ttk.Entry) -> None:
        """Close the active inline editor without changing the staged table."""
        if self._cfd_table_editor is editor:
            self._cfd_table_editor = None
            self._cfd_table_editor_filename = None
            self._cfd_table_editor_commit = None
            editor.destroy()

    def _on_cfd_table_selected(self, _event: tk.Event | None = None) -> None:
        """Commit the active cell before changing the displayed CSV."""
        if self._cfd_table_editor_commit and not self._cfd_table_editor_commit():
            if self._cfd_table_editor_filename:
                self.cfd_table_name_var.set(self._cfd_table_editor_filename)
            return
        self._render_cfd_table()

    def _validate_imported_table(self, filename: str, rows: list[list[float]]) -> None:
        """Check a selected import's standalone shape before staging it."""
        validate_cfd_table_import(filename, rows)

    def _on_cfd_tables_tab_selected(self, _event: tk.Event | None = None) -> None:
        """Reload the table view if a project load changed its active workflow."""
        if str(self.notebook.select()) != str(self.cfd_tables_tab):
            return
        self._handle_cfd_table_workflow_change()

    def _import_cfd_table(self) -> None:
        """Import one headerless numeric CSV into the currently selected table."""
        filename = self.cfd_table_name_var.get()
        source = filedialog.askopenfilename(
            title=f"Import {filename}", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not source:
            return
        try:
            rows = read_numeric_csv(source)
            self._validate_imported_table(filename, rows)
        except (OSError, ValueError) as error:
            messagebox.showerror("CSV format error", str(error))
            return
        self.cfd_table_data[filename] = rows
        self.cfd_table_dirty.add(filename)
        self._render_cfd_table()
        self._set_cfd_table_status(f"Imported {Path(source).name}; save to apply it to this workflow.")

    def _save_cfd_tables(self) -> bool:
        """Validate the complete dataset and replace staged CSVs safely."""
        if self._cfd_table_editor_commit and not self._cfd_table_editor_commit():
            self._set_cfd_table_status("Finish editing the active cell before saving.")
            return False
        if not self.cfd_table_dirty:
            self._set_cfd_table_status("There are no changes to save.")
            return True
        directory = self._cfd_tables_directory(self._cfd_tables_workflow_id)
        try:
            save_cfd_tables(directory, self.cfd_table_data, self.cfd_table_dirty)
            self.cfd_table_dirty.clear()
            self._render_cfd_table()
            self._set_cfd_table_status("All staged files passed validation and were saved.")
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save aerodynamic tables", str(error))
            self._set_cfd_table_status("Save failed; staged edits remain in the table.")
            return False

    def _discard_cfd_table_edits(self) -> None:
        """Throw away staged edits and reload the selected workflow's files."""
        if (self.cfd_table_dirty or self._cfd_table_editor is not None) and not messagebox.askyesno(
            "Discard table edits", "Discard all staged edits and reload the saved CSV files?"
        ):
            return
        if self._cfd_table_editor is not None:
            self._cancel_cfd_table_cell_edit(self._cfd_table_editor)
        self._load_cfd_tables_for_workflow()

    def _handle_cfd_table_workflow_change(self) -> bool:
        """Keep staged data safe when changing the selected workflow."""
        if not hasattr(self, "cfd_table_data"):
            return True
        selected = self.workflow_id_var.get()
        current = self._cfd_tables_workflow_id
        if not current or selected == current:
            return True
        if not self._prepare_cfd_table_workflow_change(selected):
            self._restore_cfd_workflow_selection(current)
            return False
        return True

    def _prepare_cfd_table_workflow_change(self, target_id: str) -> bool:
        """Resolve staged edits and load target tables before changing project state."""
        if self._cfd_table_editor_commit and not self._cfd_table_editor_commit():
            return False
        current = self._cfd_tables_workflow_id
        if not current or target_id == current:
            return True
        if self.cfd_table_dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved aerodynamic tables",
                "Save the staged table edits to the current workflow before switching?",
            )
            if choice is None:
                return False
            if choice and not self._save_cfd_tables():
                return False
            if not choice:
                self.cfd_table_dirty.clear()
        try:
            self._load_cfd_tables_for_workflow(target_id)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load workflow tables", str(error))
            return False
        return True

    def _restore_cfd_workflow_selection(self, workflow_id: str) -> None:
        """Restore both workflow selectors after a cancelled table switch."""
        self.workflow_id_var.set(workflow_id)
        label = next((name for name, value in self.workflow_label_to_id.items() if value == workflow_id), "")
        self.workflow_label_var.set(label)
        self._apply_workflow_mode()
