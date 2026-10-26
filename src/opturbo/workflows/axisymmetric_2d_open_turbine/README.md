# 2D axisymmetric open-turbine workflow

This workflow runs the outer domain, resolution region, actuator disk, and hub
through FreeCAD, SpaceClaim, ANSYS Meshing, and Fluent/BEM. It intentionally
creates no duct. Each run is stored as a unique candidate in the selected
project with `01_geometry/`, `02_spaceclaim/`, `03_mesh/`, and `04_cfd/` outputs.
The workflow does not create run folders under `C:\OpTurbo\Temp Files`.

```text
axisymmetric_2d_open_turbine/
├── __init__.py          # Workflow ID, title, and runner factory
├── runner.py            # Four-stage candidate pipeline and mesh-study methods
├── geometry_worker.py   # Child process entry point for FreeCAD
├── README.md            # This workflow guide
└── geometry/
    ├── __init__.py      # Geometry package marker
    ├── README.md        # Geometry subpackage and builder guide
    ├── parameters.py    # Open-turbine dimensions (domain, disk, hub)
    ├── validation.py    # Dependency-free geometry checks
    └── build_case.py    # Four duct-free STEP profiles and compound assembly

resources/workflows/axisymmetric_2d_open_turbine/
├── spaceclaim/open_turbine_assembly.scscript  # CAD cleanup and SCDOC export
├── mesh_script.py                            # Duct-free ANSYS meshing selections
└── fluent/open_turbine_assembly.cas.h5        # Fluent baseline case
```

The candidate keeps FreeCAD STEP files and its run configuration in
`01_geometry/`, the candidate-local SpaceClaim package and SCDOC in
`02_spaceclaim/`, the mesh script, Workbench project, journal, logs, and Fluent
mesh in `03_mesh/`, and the shared UDF, case, BEM tables, Fluent logs, and result
data in `04_cfd/`. Only domain, resolution, and hub sizing are used; duct sizing
and duct-wall inflation are omitted. The **Run** panel supports one candidate
or an evenly spaced TSR sweep. Sweep points use independent candidate folders,
and results can be viewed in a table or as Cp/Ct against TSR. Genetic
optimization controls are not part of this workflow. Mesh study remains
available.

The GUI hides the Design tab and source-initialization controls for this
workflow. The runner also passes conservative source initialization to the
shared CFD/BEM stage and records that normalized setting with each candidate.
