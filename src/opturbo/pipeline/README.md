# Shared pipeline support

This folder contains generic subprocess streaming, optimization overlap and
failure helpers, plus compatibility imports for the original runner path. The
actual candidate stage sequence and engineering-tool adapters are owned by
`opturbo.workflows.axisymmetric_2d.pipeline`.

New external-tool commands should live with their workflow so different CAD,
meshing, or solver choices do not become conditional branches here.
