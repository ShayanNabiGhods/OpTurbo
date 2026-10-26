# Bundled engineering resources

`resources/` holds source inputs and vendor scripts required by the selectable
engineering workflows. These are inputs; candidate-specific copies and
generated outputs are written to the selected project directory.

```text
resources/
├── README.md                              # This resource map and path policy
├── spaceclaim/                            # Ducted workflow's recorded CAD script
├── meshing/                               # Ducted ANSYS script and mesh extractor
├── fluent/                                # Shared actuator-disk UDF and build outputs
├── cfd_tables/                            # Blade geometry, airfoil polars and setup
└── workflows/axisymmetric_2d_open_turbine/ # Open workflow CAD, mesh and Fluent case
```

The existing tool scripts depend on stable resource and handoff paths. Do not
move or rename their inputs without updating the workflow's resource loading
and pipeline adapter together. New workflow assets should live under
`resources/workflows/<workflow_id>/` and be selected by that workflow. The
open-turbine workflow reuses `fluent/` and `cfd_tables/`; its `README.md`
explains the packaged SpaceClaim script, duct-free mesh script, and baseline
Fluent case.
