# CFD compatibility package

This package preserves older `opturbo.cfd.*` imports by forwarding them to
`opturbo.workflows.axisymmetric_2d.cfd`. The modules are compatibility
facades; they do not hold a parallel solver or BEM implementation.

```text
cfd/
├── __init__.py   # Public legacy CFD/BEM exports
├── bem.py        # Re-export of BEM calculation functions
├── coupling.py   # Re-export of the coupling loop
├── fluent.py     # Re-export of Fluent journal/execution helpers
├── models.py     # Re-export of CFD/BEM data classes
├── reports.py    # Re-export of report-file parser
├── resources.py  # Re-export of engineering data loaders
└── README.md     # This compatibility map
```

See `../workflows/axisymmetric_2d/cfd/README.md` for code responsibilities and
the actual implementation. New solver behavior belongs in the corresponding
workflow package.
