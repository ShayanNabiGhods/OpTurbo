# 2D axisymmetric ducted-turbine workflow

This is the current workflow selected by the Project tab. It runs FreeCAD
geometry generation, the recorded SpaceClaim preparation, ANSYS Meshing, and
Fluent with an actuator-disk BEM coupling loop.

```text
axisymmetric_2d/
├── __init__.py          # Workflow ID, resource root and stage-runner factory
├── geometry/            # Design math, preview and FreeCAD shape generation
├── cfd/                 # Fluent/BEM calculations, coupling and reports
├── pipeline/            # Candidate lifecycle, persistence and tool adapters
├── geometry_worker.py   # Child process entry point executed by FreeCAD
├── cfd_worker.py        # CFD worker prepare/run modes and result writing
├── mesh_study.py        # Mesh candidate generation and mesh-count extraction
└── README.md             # This workflow map
```

`geometry_worker.py` writes STEP artifacts for the candidate. The pipeline
then runs SpaceClaim and Meshing before invoking `cfd_worker.py`. The two
worker entry points isolate FreeCAD and Fluent's Python/runtime dependencies
from the desktop application's interpreter. `mesh_study.py` provides shared
logic for the dedicated mesh-study mode. Implementations for each stage are
described in the README files inside `geometry/`, `cfd/`, and `pipeline/`.

The workflow uses the established repository `resources/` directory to keep
the recorded SpaceClaim script and ANSYS input paths stable. Generated
candidate artifacts belong in the selected project output folder.
