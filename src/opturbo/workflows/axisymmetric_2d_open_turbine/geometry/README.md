# Open-turbine geometry

This folder contains the CAD-independent dimensions and checks plus the
FreeCAD-only STEP builder for the open-turbine workflow.

```text
geometry/
├── __init__.py     # Geometry package marker
├── parameters.py   # Domain, resolution, actuator-disk and hub dimensions and STEP names
├── validation.py   # Finite-value and containment checks before FreeCAD starts
└── build_case.py   # Build and export the four faces and duct-free compound
```

`build_case.py` reuses the established axisymmetric domain, resolution,
actuator-disk, and hub face constructors. It does not import or call the duct
builder. The parent workflow's `geometry_worker.py` runs this builder using
the configured FreeCAD command-line executable.
