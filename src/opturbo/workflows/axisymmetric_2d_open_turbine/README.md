# 2D axisymmetric open-turbine workflow

This workflow exports the outer domain, resolution region, actuator disk, and
hub as individual STEP faces and as one compound assembly. It intentionally
creates no duct. SpaceClaim remains a manual step: run the supplied
`C:\OpTurbo\Temp Files\open_turbine_assembly.scscript`, which reads the root
assembly STEP and saves the SCDOC there. Then use **Generate open-turbine mesh**
in the app to create an ANSYS mesh using the workflow mesh settings. Fluent
case creation and solving remain outside this workflow.

```text
axisymmetric_2d_open_turbine/
├── __init__.py          # Workflow ID, title, and runner factory
├── runner.py            # FreeCAD and ANSYS mesh runs, candidate records, unique handoffs
├── geometry_worker.py   # Child process entry point for FreeCAD
├── README.md            # This workflow guide
└── geometry/
    ├── __init__.py      # Geometry package marker
    ├── README.md        # Geometry subpackage and builder guide
    ├── parameters.py    # Open-turbine dimensions (domain, disk, hub)
    ├── validation.py    # Dependency-free geometry checks
    └── build_case.py    # Four duct-free STEP profiles and compound assembly

resources/workflows/axisymmetric_2d_open_turbine/mesh_script.py
    # ANSYS selections, sizing, and inflation without duct controls
```

The runner stores a self-describing candidate under the selected project and
copies all five STEP files into the next unused
`C:\OpTurbo\Temp Files\open_turbine_run_NNN\` folder. The assembly is named
`open_turbine_assembly.step` so it remains separate from the existing protected
ducted-turbine handoff. Meshing writes its candidate-owned script, journal,
logs, Workbench project, and `open_turbine_assembly.msh` under `03_mesh/`, and
copies the mesh into a new `open_turbine_mesh_run_NNN/` handoff folder. Duct-wall
sizing and duct-boundary inflation settings are omitted.
