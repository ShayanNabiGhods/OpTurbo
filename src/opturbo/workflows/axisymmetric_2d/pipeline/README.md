# Axisymmetric candidate pipeline

`runner.py` validates a candidate, creates its stage folders, coordinates the
workflow, and records results. `candidate.py` defines the prepared-candidate
record. `mesh_study.py` runs the separate mesh-study
mode against shared geometry. `adapters/` contains the direct FreeCAD,
SpaceClaim, ANSYS Workbench/Meshing, and Fluent/BEM command construction.
Shared streaming process helpers remain in `opturbo.pipeline.process`.

Inputs, generated scripts, logs, meshes, and solver results go into the chosen
project's candidate folder. Fixed SpaceClaim and Meshing handoff folders are
required by the existing recorded scripts and are copied into that folder
after each stage.
