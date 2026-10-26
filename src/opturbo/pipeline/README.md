# Shared pipeline support

This package contains services shared across the application and engineering
workflows. Concrete candidate stages are implemented in
`opturbo.workflows.axisymmetric_2d.pipeline/` for the current workflow.

```text
pipeline/
├── __init__.py   # Lazy public export of the legacy PipelineRunner
├── process.py    # Cross-platform subprocess execution and streamed logs
├── failures.py   # Error classification and low-fitness failure records
├── overlap.py    # Bounded same-generation mesh/CFD preparation overlap
└── runner.py     # Compatibility import for the 2D workflow runner
```

Use `process.py` for common process mechanics and `failures.py` for shared
failure semantics. `overlap.py` schedules work; it does not implement a CAD or
CFD stage. The new `aerodynamic_tables.py` service selects each workflow's
independent `cfd_tables` folder, validates blade geometry and the related polar
axes/matrices, and safely saves edited or imported CSV files for the
Aerodynamic Data panel. The runner facade preserves `opturbo.pipeline.runner`
imports used by older callers.
