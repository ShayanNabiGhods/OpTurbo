# External-tool stage adapters

Each adapter encapsulates one external application boundary. It receives the
runner's candidate paths and callbacks, builds the command or input files,
streams logs, and checks the expected stage output.

```text
adapters/
├── __init__.py   # Adapter package marker
├── base.py       # PipelineStage common runner/path access
├── geometry.py   # Launch FreeCAD worker and verify STEP deliverables
├── spaceclaim.py # Run fixed recorded SpaceClaim script; collect SCDOC
├── meshing.py    # Prepare Workbench project/journal; run and collect mesh
├── fluent.py     # Launch Fluent/BEM worker and validate output artifacts
└── README.md     # This adapter map
```

Adapters do not read Tk widgets or mutate project forms. The runner owns
candidate lifecycle and persistence; shared process functions live in
`opturbo.pipeline.process`. The SpaceClaim adapter depends on the supplied
recorded script and immutable handoff paths documented in
`resources/workflows/axisymmetric_2d/spaceclaim/README.md`.
