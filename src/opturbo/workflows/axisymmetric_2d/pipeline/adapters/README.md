# External-tool adapters

Each module prepares one external stage and makes its executable, command
arguments, resource paths, logs, and expected output visible: `geometry.py`
for FreeCAD, `spaceclaim.py` for CAD preparation, `meshing.py` for ANSYS, and
`fluent.py` for the Fluent/BEM worker. The stage classes use the runner's
explicit paths and log/cancel callbacks; they do not own GUI state.
