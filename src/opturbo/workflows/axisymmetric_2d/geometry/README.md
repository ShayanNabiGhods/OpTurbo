# Axisymmetric geometry package

This package owns design-parameter handling, profile calculations, GUI preview
outlines, and FreeCAD shape construction for the current workflow.

```text
geometry/
├── __init__.py        # Geometry package exports
├── config.py          # DesignParameters and generated file names
├── parameters.py      # PARSEC variable extraction and pure-Python math
├── validation.py      # FreeCAD-independent dimension checks
├── parsec.py          # Six-coefficient PARSEC curve construction
├── duct.py            # Airfoil and flanged duct profile builders
├── profiles.py        # Hub, actuator disk, domain and resolution shapes
├── freecad_helpers.py # FreeCAD shape/document/export validation helpers
├── build_case.py      # Assemble and export the full candidate STEP set
├── design_import.py   # Read design values from saved result/config files
├── preview.py          # Exact 2D outlines used by the GUI preview
└── README.md           # This module map
```

The preview and validation modules avoid importing FreeCAD, so the GUI can
validate and draw designs using ordinary Python. `build_case.py` is the CAD
assembly boundary and uses `profiles.py`, `duct.py`, and the helper wrappers to
create STEP faces. The sibling `../geometry_worker.py` is launched with the
configured FreeCAD command-line Python environment. Candidate STEP outputs are
written into that candidate's `01_geometry/` directory.
