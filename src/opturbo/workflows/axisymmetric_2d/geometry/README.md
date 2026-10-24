# Axisymmetric geometry

This folder builds the workflow's duct, hub, actuator disk, and domain shapes
through FreeCAD's `Part` and `FreeCAD` APIs. `build_case.py` assembles and
exports the STEP profiles; `duct.py`, `profiles.py`, and `parsec.py` hold the
geometry operations. `parameters.py` validates PARSEC variables,
`design_import.py` reads saved 2D designs, and
`preview.py` provides matching outlines for the GUI. The
sibling `../geometry_worker.py` launches this code inside the configured
FreeCAD command-line executable.

`duct.py` remains slightly above the module-size target because its contour
builders share FreeCAD topology and coordinate assumptions that are easier to
review together.

Final CAD shapes and candidate STEP files are stored under each project's
candidate output folder.
