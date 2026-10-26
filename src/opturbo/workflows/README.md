# Workflow implementations

Each child package is a selectable engineering workflow. A workflow chooses
its geometry worker, CAD/meshing/solver adapters, and resource root. This keeps
workflow-specific assumptions out of the shared GUI, domain models, and
process helpers.

```text
workflows/
├── __init__.py            # Public workflow lookup exports
├── selection.py           # Workflow protocol, registry and ID lookup
├── README.md               # This folder map
└── axisymmetric_2d/         # Current ducted-turbine workflow
    ├── geometry/            # PARSEC profiles, FreeCAD builders and previews
    ├── cfd/                 # Fluent/BEM model, coupling and report logic
    ├── pipeline/            # Candidate runner and external-tool adapters
    ├── geometry_worker.py   # FreeCAD process entry point
    ├── cfd_worker.py       # Fluent/BEM process entry point
    ├── mesh_study.py        # Mesh-study candidate generation/count logic
    └── __init__.py          # Workflow identity, resource root and runner factory
```

The `workflow_id` stored in a project is resolved explicitly by
`selection.py`; this is intentionally a small registry rather than dynamic
plugin discovery. The `Workflow` protocol documents the interface a workflow
must provide. Current workflow settings remain in the shared project model;
future workflow-only settings can be stored under
`ProjectConfig.workflow_settings[workflow_id]`. Bundle new workflow assets in
`resources/workflows/<workflow_id>/` and have that workflow select the folder.

`axisymmetric_2d_open_turbine/` is the geometry-only open-turbine workflow. Its
local README lists every file in the package. It creates a domain, resolution
region, actuator disk, hub, and compound STEP assembly without a duct, then
stops before SpaceClaim, meshing, or solver stages.
