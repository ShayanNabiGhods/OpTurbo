# Open-turbine meshing resource

This folder contains the ANSYS Mechanical/Meshing script used after the user
runs their manually supplied SpaceClaim script and creates
`open_turbine_assembly.scdoc`.

```text
axisymmetric_2d_open_turbine/
├── mesh_script.py  # Fluid-domain selections, sizing and optional hub inflation
└── README.md       # This resource guide
```

The workflow copies the script into each candidate's `03_mesh/` folder and
replaces its marked geometry dimensions and active mesh settings. It defines
the inlet, outlet, axis, outer wall, hub wall, resolution region, and actuator
disk selections. It contains no duct sizing or duct-wall inflation controls.
