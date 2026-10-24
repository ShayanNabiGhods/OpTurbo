# Unit tests

The tests exercise core math, persistence, workflow orchestration and selected
GUI helpers without launching Tk windows or engineering software.

```text
tests/
├── test_optimizer.py       # Genetic algorithm behavior and reproducibility
├── test_parsec.py          # PARSEC coefficient/profile calculations
├── test_preview.py         # Geometry preview outlines and matching extents
├── test_storage.py         # Atomic project/state and candidate persistence
├── test_pipeline.py        # Candidate stages, failures and result handling
├── test_overlap.py         # Same-generation preparation/CFD overlap rules
├── test_tip_loss.py        # BEM loss factors and saved project settings
├── test_turbulence_ui.py   # CFD settings and turbulence UI choices
├── test_monitor_plot.py    # Plot axes, scaling and sparse result points
└── README.md               # This test map
```

Run the suite from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Most tests use standard-library mocks and do not need FreeCAD, SpaceClaim,
ANSYS, or Fluent installed. Integration behavior still requires those programs
and valid local licenses.
