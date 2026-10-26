# 2D axisymmetric ducted-turbine resources

This folder contains every external input used by the ducted workflow.

```text
axisymmetric_2d/
├── README.md
├── spaceclaim/profile_assembly.scscript  # Recorded CAD handoff script
├── meshing/mesh_script.py                # ANSYS geometry selection and sizing
├── meshing/extract_mesh_artifact.py      # Export mesh from Workbench project
├── fluent/new_fluent_case_file.cas.h5    # Ducted baseline solver case
├── fluent/ad_sources.c                  # Actuator-disk UDF source
├── fluent/libudf/                        # UDF source and Fluent build bundle
└── cfd_tables/                           # Blade geometry and S826 polar tables
```

SpaceClaim stages a candidate-local copy of the recorded script and retains
its required fixed handoff paths and object selections. Meshing copies and
edits the mesh script into the candidate folder, then uses the extractor to
collect the mesh. The Fluent adapter copies this folder's case/UDF files and
tables into the candidate before running the coupled CFD/BEM worker. No
runtime asset is read from the open-turbine resource folder.
