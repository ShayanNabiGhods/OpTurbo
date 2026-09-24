# Changelog

## 0.0.1 — 2026-09-08

- Changed the Project tab to a compact two-column layout.
- Rebuilt the whole-domain preview from the exact FreeCAD profile equations,
  including the quarter-circle resolution inlet, rounded hub, actuator
  thickness, duct, and outer domain.
- Added duct angle of attack and chord length as selectable GA variables.
- Disabled and grayed all unticked design-variable fields.
- Replaced the Workflow sub-tabs with one two-column settings page and removed
  the SpaceClaim settings page; the fixed script contract remains protected.
- Replaced the Monitor sub-tabs with a two-column dashboard: live log on the
  left and the two plots stacked on the right.
- Added explicit Fluent divergence and non-finite-result detection.
- Corrected mesh replacement to Fluent's `/mesh/replace` TUI command.
- Added a CFD option to retain or discard every outer-iteration solution file.
- Reorganized the former four-step integration copies into one standalone
  application package plus a shared resource tree.
- Moved Workbench scratch files to a short fixed staging path to avoid failures
  caused by deeply nested candidate paths.
- Added an end-to-end small optimization script for reproducible validation.
