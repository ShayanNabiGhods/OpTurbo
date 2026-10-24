# Domain models

This folder defines saved project settings, design variables, workflow input
validation, and valid Fluent setting values. It has no Tkinter or vendor-tool
dependency. The GUI reads and validates these models before saving; the
axisymmetric pipeline validates them again before starting external tools.

`ProjectConfig` keeps the existing 2D settings fields for saved-project
compatibility and carries future workflow options under
`workflow_settings[workflow_id]`.

`models.py` at the package root re-exports these types for older imports.
