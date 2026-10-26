# 2D axisymmetric open-turbine resources

This folder contains all inputs needed to run the open workflow independently
of the ducted workflow.

```text
axisymmetric_2d_open_turbine/
├── README.md
├── spaceclaim/open_turbine_assembly.scscript  # Recorded duct-free CAD preparation
├── meshing/mesh_script.py                     # Open-domain selections and sizing
├── meshing/extract_mesh_artifact.py           # Workbench mesh exporter
├── fluent/open_turbine_assembly.cas.h5        # Open-turbine baseline case
├── fluent/ad_sources.c                        # Local actuator-disk UDF source copy
├── fluent/libudf/                             # Local Fluent UDF bundle copy
└── cfd_tables/                                # Local blade and airfoil data copy
```

The runner uses the local SpaceClaim and mesh scripts, baseline case, UDF
files, extractor, and blade/polar tables. It stages candidate-specific files
in the selected project folder; it does not create run folders in
`C:\OpTurbo\Temp Files`.
