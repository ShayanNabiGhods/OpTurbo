# Tkinter interface

This package builds the desktop UI from small view and behavior mixins. GUI code
collects user choices, displays results, and starts worker services. Project
models, CFD/BEM calculations, and vendor command construction are implemented
outside this package.

```text
gui/
├── __init__.py                 # Presentation package marker
├── window.py                   # Tk root, shared state and mixin composition
├── layout.py                   # Menus and primary notebook layout
├── project_view.py             # Project selection, paths and project actions
├── design_form.py              # Duct family and design-variable controls
├── config_editor.py             # PARSEC/design parameter editing behavior
├── design_preview.py           # Preview refresh and design-field wiring
├── duct_preview.py             # Canvas drawing for duct/domain outlines
├── workflow_settings.py        # Workflow settings tab assembly
├── settings_form.py            # Dataclass settings forms and value binding
├── mesh_study_view.py          # Mesh-study tab and table/view coordination
├── mesh_study_settings.py      # Mesh-study variable selection and settings
├── mesh_study_table.py         # Mesh-study results table refresh
├── mesh_study_run.py           # Mesh-study start/stop UI actions
├── mesh_study_worker.py        # Mesh-study background-thread coordination
├── optimization_view.py        # Optimization tab layout
├── optimization_controls.py    # GA controls, validation and run-state buttons
├── optimization_worker.py     # Background optimization worker lifecycle
├── monitor_view.py             # Monitor tab and result panels
├── monitor_results.py          # Candidate/history event ingestion and updates
├── simple_bem_view.py          # Standalone TSR sweep form, table and Cp/Ct plot
├── aerodynamic_data_view.py    # Workflow-aware editor/importer for blade and airfoil CSV tables
├── accessibility_view.py       # Accessibility preferences UI
├── appearance.py               # Runtime theme and numeric-entry behavior
├── labels.py                   # Field labels and concise help descriptions
├── choices.py                  # GUI setting groups and selectable values
├── constants.py                # Compatibility exports for UI constants
├── configuration.py            # Saved-vs-requested configuration comparison
├── pdf_help.py                 # Open the bundled manual and theory PDFs
├── plot.py                     # Dependency-free Tk canvas plots
├── scrolling.py                # Scrollable settings frame
├── tooltips.py                 # Hover tooltip widget
└── widgets.py                  # Compatibility exports for reusable widgets
```

The root window composes focused mixins so each tab's controls stay near their
event handlers. Mixins share state through the root window instance. Keep
engineering validation in `opturbo.domain` and external execution in the
workflow pipeline; UI modules should not call FreeCAD, SpaceClaim, Meshing, or
Fluent directly. `simple_bem_view.py` reads the current flow and rotor fields,
then calls `opturbo.simple_bem` with the selected workflow's blade and polar
tables. This panel runs locally and does not start the engineering workflow.
`aerodynamic_data_view.py` presents the workflow's blade and polar CSV files in
a dataset sidebar beside the selected table, format notes, and edit/import
actions. It calls `opturbo.pipeline.aerodynamic_tables` to load, validate, and
save the selected workflow's resources. It stages edits and writes them only
after the blade and polar tables pass cross-file validation;
the exact formats are in `docs/manual.md` under Aerodynamic Data. The single Help
button in the top header opens the user manual;
the Help menu retains the theory guide and About dialog.

The Project workflow selector also offers an open-turbine run workflow. It
executes the packaged SpaceClaim script, creates a duct-free ANSYS mesh, then
runs the Fluent/BEM evaluation. Candidate artifacts stay in the selected
project folder. The Design tab is hidden and the Optimization tab becomes a
simple Run panel, with no GA controls; mesh study remains available. Duct
design, duct mesh sizing, and source-initialization controls are hidden for
this workflow, which always uses conservative source initialization. Automatic
mesh studies use evenly spaced values only. The Monitor hides the candidate-
history plot for this workflow. Its run table fits visible columns to the
available width, and its Cp/Ct chart follows the active application theme.
