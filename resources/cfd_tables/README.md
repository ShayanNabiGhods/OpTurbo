# CFD and BEM input tables

These text files provide the aerodynamic data loaded by
`opturbo.workflows.axisymmetric_2d.cfd.resources`. The worker copies this
directory into each candidate's `04_cfd/resources/` folder before calculation.

```text
cfd_tables/
├── metadata.json       # Rotor/flow setup: radii, blade count, speed and air
├── ntnu_geometry.csv   # Radial blade geometry rows used to build blade model
├── s826_alpha.csv      # Angle-of-attack grid for S826 polar tables (degrees)
├── s826_re.csv         # Reynolds-number grid for polar-table columns
├── s826_cl.csv         # Lift coefficient table indexed by alpha and Reynolds
├── s826_cd.csv         # Drag coefficient table indexed by alpha and Reynolds
└── README.md           # This resource/data map
```

The S826 polar CSVs are numeric matrices: alpha samples provide rows and the
Reynolds grid provides corresponding columns. Keep the alpha, Reynolds, lift,
and drag dimensions aligned. `ntnu_geometry.csv` is a numeric row table
consumed by the loader; `metadata.json` supplies operating/setup values and is
read alongside the tables. Do not place run-specific or generated values here;
those belong with each candidate's copied CFD resources and result files.
