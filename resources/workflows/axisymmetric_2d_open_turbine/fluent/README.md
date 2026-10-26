# Open-turbine Fluent resources

The open-workflow Fluent stage starts from
`open_turbine_assembly.cas.h5`, copies this folder's actuator-disk UDF bundle,
and runs the candidate-local CFD/BEM coupling. The UDF source and `libudf/`
tree are independent copies of the ducted workflow's shared coupling
implementation; the open runner does not read files from that workflow.

```text
fluent/
├── README.md
├── open_turbine_assembly.cas.h5  # Open-turbine Fluent setup
├── ad_sources.c                  # Actuator-disk UDF source
└── libudf/                       # Source and Fluent build bundle
```

Generated candidate logs, iteration data, and results stay in the selected
project. Rebuild the UDF bundle with the installed Fluent version if its build
target or source changes.
