# CFD compatibility imports

This package forwards the original `opturbo.cfd.*` import paths to the
2D axisymmetric Fluent/BEM implementation in
`opturbo.workflows.axisymmetric_2d.cfd`. New workflows can select their own
solver and aerodynamic modules without changing these compatibility imports.
