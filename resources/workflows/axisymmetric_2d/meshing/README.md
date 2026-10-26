# Ducted workflow meshing resources

- `mesh_script.py` defines the ducted ANSYS Meshing selections and sizing
  settings. The adapter copies it to each candidate and substitutes active
  project settings.
- `extract_mesh_artifact.py` exports the generated mesh artifact from a
  Workbench project into the candidate folder.

The open-turbine workflow has its own copies under its own `meshing/`
directory.
