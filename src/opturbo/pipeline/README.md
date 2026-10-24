# Shared pipeline support

This package contains helpers shared across engineering workflows. It should
not know the details of a duct shape, mesh script, or solver command. Concrete
candidate stages are implemented in
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
CFD stage. Workflow adapters should own commands, input files, and output
checks. The runner facade preserves `opturbo.pipeline.runner` imports used by
older callers.
