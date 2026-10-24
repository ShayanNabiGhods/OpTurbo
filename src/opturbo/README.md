# OpTurbo package

This package holds the Tkinter application, shared project and optimization
logic, persistence, and workflow implementations. `app.py` is the stable GUI
entry point; `workflows/selection.py` maps saved workflow IDs to their concrete
implementations. The `geometry/` and `cfd/` packages, plus
`pipeline/runner.py`, preserve imports used by older callers.

The active 2D workflow is under `workflows/axisymmetric_2d/`. Its workers run
FreeCAD and Fluent in separate processes. The application also uses Tkinter
from Python's standard library; no third-party GUI package is required.
