# Axisymmetric CFD and BEM

This folder owns the current Fluent/BEM coupling: BEM models and calculations,
Fluent journal generation and process control, report parsing, and resource
loading. It uses the packaged airfoil and blade tables plus a Fluent baseline
case. The `cfd_worker.py` process entry point loads resources copied into each
candidate's `04_cfd/` folder, then coordinates the solver and BEM loop. The
sibling `../cfd_worker.py` is the process entry point.

Another workflow can choose different solver modules and data without
changing this package.
