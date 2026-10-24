# Fluent baseline and UDF resources

The CFD worker copies these source resources into each candidate's `04_cfd/`
folder before running Fluent. Candidate logs, iteration data, and final case
files stay with that candidate; the checked-in baseline is treated as input.

```text
fluent/
├── README.md                      # This resource map
├── new_fluent_case_file.cas.h5    # Baseline Fluent case and solver setup
├── ad_sources.c                   # Fluent actuator-disk source UDF
└── libudf/
    ├── src/ad_sources.c           # Editable UDF source copy
    ├── win64/2ddp_host/            # Fluent-generated 2D double host files
    └── win64/2ddp_node/            # Fluent-generated 2D double compute files
```

The UDF and generated `libudf` artifacts must match the Fluent version and
build target used for a run. See `libudf/README.md` for the generated-folder
layout. Regenerate build artifacts using the installed ANSYS Fluent toolchain;
do not edit generated headers by hand.
