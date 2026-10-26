# 2D axisymmetric open-turbine workflow

This geometry-only workflow exports the outer domain, resolution region,
actuator disk, and hub as individual STEP faces and as one compound assembly.
It intentionally creates no duct and currently stops before SpaceClaim,
meshing, and CFD.

```text
axisymmetric_2d_open_turbine/
├── __init__.py          # Workflow ID, title, and runner factory
├── runner.py            # FreeCAD invocation, candidate records, unique STEP handoff
├── geometry_worker.py   # Child process entry point for FreeCAD
├── README.md            # This workflow guide
└── geometry/
    ├── __init__.py      # Geometry package marker
    ├── README.md        # Geometry subpackage and builder guide
    ├── parameters.py    # Open-turbine dimensions (domain, disk, hub)
    ├── validation.py    # Dependency-free geometry checks
    └── build_case.py    # Four duct-free STEP profiles and compound assembly
```

The runner stores a self-describing candidate under the selected project and
copies all five STEP files into the next unused
`C:\OpTurbo\Temp Files\open_turbine_run_NNN\` folder. The assembly is named
`open_turbine_assembly.step` so it remains separate from the existing protected
ducted-turbine handoff. No SpaceClaim script is read or edited by this workflow.
