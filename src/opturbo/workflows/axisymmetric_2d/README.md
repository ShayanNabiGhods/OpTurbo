# 2D axisymmetric workflow

This workflow preserves the existing ducted-turbine process: FreeCAD geometry,
SpaceClaim preparation, ANSYS Meshing, then Fluent/BEM. `__init__.py` identifies
the workflow and selects its runner and resource root. Engineering settings
and validation are shared through `opturbo.domain`; geometry, CFD, mesh-study
generation, and stage coordination remain specific to this workflow.

`geometry_worker.py` and `cfd_worker.py` are its process entry points. Root
level worker scripts remain as compatibility launchers.

The current resource root is the repository's existing `resources/` directory
to preserve recorded scripts and vendor-file paths. Candidate outputs are
written only to the selected project folder.
