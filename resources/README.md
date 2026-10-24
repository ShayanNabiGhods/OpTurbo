# Bundled engineering resources

`resources/` holds source inputs and vendor scripts required by the current
axisymmetric workflow. The workflow resolves this directory as its resource
root. These are inputs; candidate-specific copies and generated outputs are
written to the selected project directory.

```text
resources/
├── README.md           # This resource map and path policy
├── spaceclaim/         # Recorded SpaceClaim assembly preparation script
├── meshing/            # ANSYS Meshing script and mesh artifact extractor
├── fluent/             # Baseline Fluent case and UDF source/build files
└── cfd_tables/         # Blade geometry, airfoil polars and setup metadata
```

The existing tool scripts depend on stable resource and handoff paths. Do not
move or rename their inputs without updating the workflow's resource loading
and pipeline adapter together. New workflow assets should live under
`resources/workflows/<workflow_id>/` and be selected by that workflow.
