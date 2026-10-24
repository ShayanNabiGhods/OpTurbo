# Fluent `libudf` layout

This directory contains the editable actuator-disk source and the 64-bit
Fluent-generated host/node build trees. The generated artifacts are specific
to Fluent's Windows 2D double-precision target.

```text
libudf/
├── README.md
├── src/
│   ├── README.md
│   └── ad_sources.c              # Editable source of actuator-disk terms
└── win64/
    ├── 2ddp_host/                # Host-side library and generated sources
    │   ├── ad_sources.c/.obj
    │   ├── udf_names.c/.obj
    │   ├── ud_io1.h
    │   ├── libudf.dll/.lib
    │   ├── resolve.exe
    │   ├── SConstruct, scons.bat
    │   └── user.txt
    └── 2ddp_node/                # Compute-node counterparts
        ├── ad_sources.c/.obj
        ├── udf_names.c/.obj
        ├── ud_io1.h
        ├── libudf.dll/.lib
        ├── resolve.exe
        ├── SConstruct, scons.bat
        └── user.txt
```

The `.c` file in `src/` is the source of truth for manual code edits. The
copies, headers, object files, libraries and build scripts under `win64/` are
Fluent build outputs and should be regenerated together through the matching
ANSYS installation after source changes.
