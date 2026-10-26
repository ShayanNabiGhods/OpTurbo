# Open-turbine meshing resource

Resources for the duct-free 2D axisymmetric open-turbine workflow. The app
runs the packaged SpaceClaim script against each candidate's geometry, creates
the mesh, then evaluates the Fluent/BEM coupling. Candidate artifacts are kept
in the selected project; no run directories are created under `Temp Files`.

```text
axisymmetric_2d_open_turbine/
├── README.md                            # This resource guide
├── mesh_script.py                       # Fluid-domain selections and duct-free sizing
├── fluent/
│   └── open_turbine_assembly.cas.h5     # Open-turbine Fluent baseline case
└── spaceclaim/
    └── open_turbine_assembly.scscript   # Recorded open-turbine CAD preparation
```

The workflow writes a candidate-local copy of the SpaceClaim package with only
its fixed STEP and SCDOC paths redirected into `01_geometry/` and
`02_spaceclaim/`. The mesh script is copied to `03_mesh/` with configured
settings applied. It defines the inlet, outlet, axis, outer wall, hub wall,
resolution region, and actuator disk selections without duct controls.

The Fluent stage uses this open-turbine baseline case and the shared actuator
disk UDF and blade/polar tables from `resources/fluent/` and
`resources/cfd_tables/`. The shared UDF is not duplicated for the open workflow.
