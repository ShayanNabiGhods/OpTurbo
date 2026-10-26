# `opturbo` package map

This package contains the desktop application and its engineering workflow.
Keep user-interface code in `gui/`, shared serializable settings in `domain/`,
workflow-neutral process helpers in `pipeline/`, and workflow-specific CAD,
mesh, solver, and stage code below `workflows/<workflow_id>/`.

```text
opturbo/
├── __init__.py                 # Package metadata
├── app.py                      # Public GUI entry point and legacy exports
├── gui/                        # Tkinter interface; see gui/README.md
├── domain/                     # Project/design/mesh/CFD/GA models; see README
├── workflows/
│   ├── selection.py            # Saved workflow ID to implementation lookup
│   └── axisymmetric_2d/         # Current FreeCAD → SpaceClaim → Meshing → CFD
├── pipeline/                   # Process helpers and workflow-aware aerodynamic CSV operations
├── simple_bem.py               # CFD-free BEM induction solver and TSR sweeps
├── geometry/                   # Compatibility exports for 2D geometry
├── cfd/                        # Compatibility exports for 2D CFD/BEM
├── objectives.py               # Objective labels and candidate fitness values
├── optimizer.py                # Reproducible real-valued genetic algorithm
├── storage.py                  # Atomic project and run-result persistence
├── paths.py                    # Stable application/resource root discovery
├── models.py                   # Legacy exports for shared domain models
├── parsec.py                   # Legacy exports for PARSEC calculations
├── preview.py                  # Legacy exports for 2D preview outlines
├── design_import.py            # Legacy exports for saved-design loading
├── mesh_study.py               # Legacy exports for mesh-study utilities
├── geometry_worker.py          # Legacy FreeCAD worker launcher
└── cfd_worker.py               # Legacy Fluent/BEM worker launcher
```

The GUI calls engineering work through the selected workflow runner. The root
worker scripts and facade packages exist to preserve historical entry points;
their implementations live in `workflows/axisymmetric_2d/`. Candidate data is
written through the storage and workflow saving layers to the user's selected
project directory, outside this source tree. The standalone `simple_bem.py`
solver uses the shared BEM model and the selected workflow's polar tables to
calculate a TSR sweep without launching a workflow, building a duct, or
invoking CFD. The GUI's Aerodynamic Data tab delegates table loading, format
checks, and writes to `pipeline/aerodynamic_tables.py`.
