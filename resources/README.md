# Workflow resources

All source assets used by an engineering workflow live under its own folder in
`resources/workflows/`. The app selects that folder from the workflow ID;
runtime code does not fall back to another workflow's files. Candidate outputs
are copied into the selected project folder.

```text
resources/
├── README.md
└── workflows/
    ├── axisymmetric_2d/
    │   ├── spaceclaim/
    │   ├── meshing/
    │   ├── fluent/
    │   └── cfd_tables/
    └── axisymmetric_2d_open_turbine/
        ├── spaceclaim/
        ├── meshing/
        ├── fluent/
        └── cfd_tables/
```

The two Fluent/UDF and CFD-table trees are independent copies. Update both
copies deliberately when a shared engineering input changes. The ducted
recorded SpaceClaim script must retain its fixed STEP/SCDOC paths and object
selections. See each workflow README for the files and their roles.
