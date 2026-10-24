# Axisymmetric CFD and BEM package

This package implements the actuator-disk blade-element/momentum calculation
and its iterative coupling to Fluent. Resource loaders convert the bundled
CSV/JSON tables into model objects; Fluent reports and convergence data are
collected by the worker for each candidate.

```text
cfd/
├── __init__.py   # Public CFD/BEM exports
├── models.py     # Flow, turbine, blade, airfoil and result data containers
├── resources.py  # CSV/JSON readers and engineering-table model construction
├── bem.py        # Airfoil interpolation, rotor loads and performance metrics
├── fluent.py     # Fluent journal generation and persistent solver execution
├── reports.py    # Parse numeric Fluent report files
├── coupling.py   # Initialize, relax and iterate BEM source terms with CFD
└── README.md     # This package map
```

`coupling.py` coordinates the loop: prepare source terms, run the Fluent
iteration, read flow reports, solve the BEM model, relax updated sources, and
stop on convergence or configured limits. `bem.py` and `fluent.py` perform the
two sides of that loop. `cfd_worker.py` one level above prepares copied
resources or executes the candidate calculation. The pipeline adapter writes
logs and result artifacts under `04_cfd/`.
