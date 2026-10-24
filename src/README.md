# Python source tree

`src/` contains the installable `opturbo` package. `run.py` adds this directory
to the import path when starting from a source checkout. The package is divided
into the application shell, shared domain and pipeline helpers, and selectable
engineering workflows.

```text
src/
├── README.md                 # This map of the Python source root
└── opturbo/
    ├── app.py                # Public application entry point
    ├── gui/                  # Tkinter windows, views, controls and widgets
    ├── domain/               # Settings data models and validation
    ├── pipeline/             # Shared process, failure and overlap helpers
    ├── workflows/            # Workflow registry and workflow implementations
    ├── geometry/             # Legacy geometry import facade
    ├── cfd/                  # Legacy CFD import facade
    ├── optimizer.py          # Genetic algorithm
    ├── objectives.py         # Objective selection and fitness extraction
    ├── storage.py            # Project and candidate persistence
    ├── paths.py              # Application and bundled-resource paths
    └── [compatibility modules] # Old import/worker paths retained for callers
```

## How the package is layered

The GUI reads and edits domain models, then delegates calculations and external
program execution through the selected workflow's pipeline. Workflow code owns
geometry, meshing, and solver-specific behavior. Shared helpers in `pipeline/`
provide process streaming and optimization overlap without knowing the
engineering workflow. `opturbo.geometry`, `opturbo.cfd`, and several top-level
modules remain thin facades for older import paths; new engineering code belongs
under `opturbo.workflows/<workflow_id>/`.

For the per-file map, see [the package guide](opturbo/README.md), then the
README in the relevant subdirectory. The source code targets Python 3.10+ and
uses the standard library for the application and core workflow logic.
