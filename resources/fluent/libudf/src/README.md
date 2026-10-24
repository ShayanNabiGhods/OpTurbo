# Editable Fluent UDF source

```text
src/
├── ad_sources.c   # Actuator-disk source-term UDF compiled by Fluent
└── README.md      # This source directory guide
```

`ad_sources.c` defines the Fluent user-defined source functions used to apply
the actuator-disk momentum terms. Edit this copy, then rebuild the host and
node libraries under `../win64/` with the Fluent version and 2D double
precision target configured for the workflow. The generated build copies are
not the preferred place for source edits.
