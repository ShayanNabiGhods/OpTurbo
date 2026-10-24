# Geometry compatibility package

This package preserves the historical `opturbo.geometry.*` import path. Every
module re-exports the matching implementation from
`opturbo.workflows.axisymmetric_2d.geometry`; it contains no second geometry
implementation.

```text
geometry/
├── __init__.py        # Package-level legacy exports
├── build_case.py      # Re-export of STEP case builder
├── config.py          # Re-export of design parameters and output names
├── duct.py            # Re-export of duct profiles
├── freecad_helpers.py # Re-export of FreeCAD wrappers
├── parsec.py          # Re-export of PARSEC curve functions
├── profiles.py        # Re-export of hub/disk/domain profile builders
├── validation.py      # Re-export of geometry validation
└── README.md          # This compatibility map
```

Implementations and explanations live in
`../workflows/axisymmetric_2d/geometry/`. Add new workflow geometry there (or
under its own workflow package), not in this facade.
