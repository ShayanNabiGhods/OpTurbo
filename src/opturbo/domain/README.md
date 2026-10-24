# Shared domain models

These dataclasses and validation helpers describe settings independent of Tk
and vendor executables. The GUI edits them; a workflow validates them again
before starting expensive external tools.

```text
domain/
├── __init__.py       # Curated public model exports
├── project.py        # ProjectConfig serialization and old-project defaults
├── design.py         # Duct settings, design variable specs and defaults
├── mesh.py           # ANSYS Meshing settings and mesh-study defaults
├── cfd.py            # Fluent and BEM configuration fields
├── optimization.py   # Genetic-algorithm configuration
├── tools.py          # External executable paths and fixed handoff paths
├── accessibility.py  # Saved accessibility/theme preferences
├── choices.py        # Allowed CFD values shared by UI and validators
└── validation.py     # Cross-field/range checks before pipeline launch
```

`ProjectConfig` is the persisted top-level settings object. It retains the
current axisymmetric fields for backward compatibility and has a
`workflow_settings` mapping for future workflow-specific options. Keep these
models serializable and free of Tk widgets, process handles, or FreeCAD/Fluent
objects. `opturbo.models` re-exports legacy public names.
