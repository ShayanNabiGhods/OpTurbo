# Fluent resources

This folder contains the baseline Fluent case and UDF source/build files used
by the axisymmetric Fluent/BEM worker. The runner copies these inputs into each
candidate's `04_cfd/fluent/` folder before starting Fluent. Candidate logs,
iteration data, and final cases stay with that candidate's results.

`libudf/` contains the checked-in UDF source and Windows host/node build
artifacts. Treat these vendor-generated files as inputs; rebuild them only
through the matching ANSYS toolchain.
