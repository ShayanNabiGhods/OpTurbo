# Axisymmetric candidate pipeline

This package owns the stage sequence for one candidate. It validates the
configuration, assigns candidate output locations, runs the geometry/CAD/mesh
stages, then runs Fluent/BEM and records success or failure.

```text
pipeline/
├── __init__.py      # Public runner and prepared-candidate exports
├── candidate.py     # PreparedCandidate record passed between stages
├── runner.py        # Candidate lifecycle, stage order and result recording
├── mesh_study.py    # Mesh-study stage operations and result collection
├── adapters/
│   ├── base.py      # Runner-owned paths, callbacks and stage interface
│   ├── geometry.py  # FreeCAD command setup and STEP-output verification
│   ├── spaceclaim.py # Recorded script execution and SCDOC collection
│   ├── meshing.py   # Workbench/Meshing scripts, journal and mesh export
│   └── fluent.py    # Candidate CFD worker invocation and result checks
└── README.md        # This package map
```

The runner composes the adapters in pipeline order; adapters receive paths,
logging, and cancellation behavior from the runner instead of owning GUI state.
Shared process streaming and overlap scheduling are in
`opturbo.pipeline/`. Generated scripts, logs, mesh and solver files are saved
with the candidate. Fixed vendor handoff directories required by the recorded
SpaceClaim and Meshing scripts are copied into the candidate archive after
their stages complete.
