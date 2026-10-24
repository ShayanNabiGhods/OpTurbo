# ANSYS Meshing resources

These source files configure the workflow mesh and extract the Fluent mesh
artifact from a Workbench project. The pipeline prepares candidate-specific
copies under `03_mesh/`; source files here remain bundled inputs.

```text
meshing/
├── mesh_script.py             # ANSYS Meshing sizing, methods and named regions
├── extract_mesh_artifact.py   # Find/copy the produced Fluent mesh artifact
└── README.md                  # This resource map
```

`mesh_script.py` is executed in the ANSYS Meshing/Workbench environment and
uses the candidate geometry and configured sizing controls. The extractor is
called after meshing to collect the `.msh` output expected by Fluent. Keep
changes aligned with the adapter in
`src/opturbo/workflows/axisymmetric_2d/pipeline/adapters/meshing.py`.
