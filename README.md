# OpTurbo

OpTurbo is a Windows desktop application for designing, evaluating, and
optimizing ducted and open wind turbines. It connects a Tkinter interface to
four-stage engineering workflows: FreeCAD geometry, SpaceClaim, ANSYS Meshing,
and Fluent/BEM. Ducted designs can use the genetic algorithm; the open-turbine
workflow runs one performance evaluation at a time and keeps mesh study.

## Start the application

Use Windows Python 3.10 or newer:

```powershell
cd "C:\Project Saves\Python Codes\OpTurbo"
python run.py
```

## Citing OpTurbo

If OpTurbo is used in your research, please cite the software
and specify the version used to ensure reproducibility.

**Recommended citation:**

Shayan, Nabi Ghods. *OpTurbo*. Zenodo.
https://doi.org/10.5281/zenodo.23621604

### BibTeX

```bibtex
@software{shayannabighods_opturbo,
  author  = { Nabi Ghods, Shayan},
  title   = {{OpTurbo}},
  doi     = {10.5281/zenodo.23621604},
  url     = {https://doi.org/10.5281/zenodo.23621604},
  license = {GPL-3.0-only}
}
```

Please cite OpTurbo when it materially contributes to the
methods, computational workflow, or results of your research.

## Documentation

The **Help** button at the top of the application opens the complete
[User Manual](docs/manual.pdf). The **Help** menu also contains the
[Theory Guide](docs/theory.pdf). The Markdown sources are in `docs/`; regenerate
both PDFs with `python scripts/build_documentation.py`.

Tkinter is included with the standard Windows Python installer. Check the
executable paths on the **Project** tab before running. The default paths are
  configured for FreeCAD 1.1 and ANSYS `v242`, matching the defaults in the
project model. Choose a workflow save
folder outside the source-code folder, for example
`C:\OpTurbo\Projects\baseline-study`.

## Application workflow

- **Project** — select the engineering workflow, set the project name and
  results folder, and configure external application paths.
- **Design** — choose an airfoil or flanged duct and select which design
  variables the optimizer may change. Unselected variables stay fixed. The
  geometry and domain previews update with the design.
- **Workflow Settings** — configure geometry, meshing, and CFD/BEM. Meshing
  settings include global and local sizing, growth rate, CPU cores, and method.
  CPU cores can be **Program Controlled** or explicitly selected. The method
  can be **Default (ANSYS automatic)**, **Quad**, **Tri**, or **MultiZone**.
  SpaceClaim uses its supplied recorded script and is not edited in the GUI.
  CFD/BEM settings include turbulence models and their residual criteria,
  discretization, pressure-velocity coupling, iteration controls, and loss
  correction.
- **Simple BEM** — calculate a rotor-only performance curve without launching
  geometry, duct/domain design, meshing, or CFD. The panel uses current flow
  and rotor values, the active workflow's NTNU blade geometry and S826 airfoil polars,
  a selectable tip-loss correction, and a user-defined TSR interval. Results
  appear side-by-side in a table on the left and a Cp/Ct plot on the right.
- **Aerodynamic Data** — edit or import the active workflow's blade-section
  geometry and airfoil lift/drag CSV tables. The panel checks numeric values,
  section ordering, polar axes, and matrix dimensions before saving. A dataset
  list and row counts sit beside the selected table and its format notes. See the
  [manual's CSV format guide](docs/manual.md#aerodynamic-data) for exact layouts.
- **2D axisymmetric open turbine** → generate the domain, resolution region,
  actuator disk, and hub as STEP files and one open-turbine assembly, without
  creating a duct. Run FreeCAD, the packaged SpaceClaim script, ANSYS Meshing,
  and Fluent/BEM to evaluate one design. Results stay in the selected project's
  candidate folder. The workflow hides the Design tab, has no genetic
  optimization controls, and always uses conservative CFD source
  initialization. Its Run panel also supports repeated CFD/BEM evaluations across a user-defined TSR range, with a switch between the run table and a Cp/Ct-versus-TSR plot; mesh study remains available.
- **Mesh Study** → compare full CFD/BEM candidates using an evenly spaced sweep
  across the selected bounds. All enabled values advance together from their
  minimums to maximums.
- **Optimization** — evaluate the current design, configure and start the
  genetic algorithm, resume a saved run, and review candidate results. A run
  can be stopped safely; active Fluent work and any active overlap preparation
  are allowed to finish.
- **Monitor** — review candidate histories, BEM distributions, live residuals,
  and outer-iteration `Cp`/`Ct` plots in separate views. Candidate history is
  hidden for open-turbine runs, whose results appear in the Run panel.

## Candidate pipeline

The ducted workflow passes each candidate through these stages:

1. **FreeCAD** creates the selected duct geometry and exports STEP files to
   that candidate's results directory.
2. **SpaceClaim** runs the supplied recorded script against the assembly and
   saves its document with the candidate artifacts. The script depends on
   recorded body and face identities, so major topology changes can invalidate
   it.
3. **ANSYS Meshing** runs a candidate-specific Workbench journal and mesh
   script, then exports `axisymmetric_mesh.msh`. In Default method mode, the
   script leaves the meshing method to ANSYS. The CPU setting likewise supports
   ANSYS's Program Controlled default.
4. **Fluent/BEM** loads the baseline case, replaces its mesh, runs the coupled
   calculation, and saves results. Optional outer-iteration solution files
   can be retained for later inspection.

Failed candidates are recorded with diagnostic details in their candidate
folder and assigned a low fitness so the remaining optimization can continue.

The **2D axisymmetric open turbine** workflow runs all four stages and records
geometry, SpaceClaim, mesh, Fluent/BEM results, and logs under the selected
project's standard candidate layout. Its mesh script uses domain, resolution,
and hub sizing and omits duct sizing and duct-wall inflation. It uses the
workflow's open-turbine Fluent baseline case and shares the ducted workflow's
UDF and BEM tables. It creates no run directories under `C:\OpTurbo\Temp Files`.

### Overlap preparation

The optional experimental overlap setting prepares the next candidate through
meshing while the current candidate runs Fluent. It applies within one
generation. The next Fluent run waits until its mesh preparation has finished,
so Fluent cannot start against an incomplete mesh. This mode uses additional
memory and may require concurrent ANSYS licenses.

## Optimization and recovery

The genetic algorithm uses real-valued design variables, tournament selection,
arithmetic crossover, Gaussian mutation, bounds clamping, and elitism. Its
random seed makes a run reproducible. Start with a small population and a small
number of generations, and use **Evaluate current design** to check the local
engineering-software setup first.

**Resume previous optimization** continues from saved state. Completed
candidate results are reused; only candidates without saved results are
evaluated again. Resume requires workflow settings to match the saved run.
Project settings, optimization history, and resume state are stored in the
selected project folder.

## BEM loss correction

The tip-loss choices are Prandtl and Bontempo. Bontempo is the default. The
Bontempo correction uses the empirical coefficients exposed in the GUI and
saved with project settings. Its tip factor is combined with the conventional
Prandtl root-loss factor, so root loss remains active. The correction is a
duct-specific calibration and may not apply to every optimized geometry.

## Results layout

```text
chosen-project-folder/
├── opturbo_project.json
├── optimization_history.json
├── optimization_state.json
├── run_history.json              # Open-turbine performance runs
├── best/
├── logs/
├── exports/
└── candidates/
    └── generation_001/
        └── candidate_001/
            ├── candidate.json
            ├── result.json       # or failure.json
            ├── 01_geometry/
            ├── 02_spaceclaim/
            ├── 03_mesh/
            └── 04_cfd/
```

Candidate directories preserve pipeline inputs, outputs, and logs for review.
Repeated evaluations use a new run directory rather than replacing an existing
candidate's artifacts. Open-turbine runs are listed in `run_history.json` and
do not create genetic-optimization state.

## Source layout

```text
run.py
src/opturbo/
├── app.py                         # Public GUI entry point and compatibility exports
├── gui/                           # Window, settings forms, design previews, result views
├── simple_bem.py                  # CFD-free induction solver and TSR sweep
├── domain/                        # Project models and engineering-input validation
├── workflows/
│   ├── selection.py               # Explicit workflow ID to implementation map
│   └── axisymmetric_2d/
│       ├── geometry/              # FreeCAD shapes, design math, and previews
│       ├── cfd/                   # Fluent journals and BEM coupling
│       ├── mesh_study.py          # Axisymmetric mesh study design/count logic
│       ├── geometry_worker.py     # FreeCAD process entry point
│       ├── cfd_worker.py          # Fluent/BEM process entry point
│       └── pipeline/
│           ├── runner.py          # Candidate stage coordination
│           └── adapters/          # FreeCAD, SpaceClaim, Meshing, Fluent commands
├── pipeline/                      # Shared process helpers and aerodynamic CSV services
├── geometry/, cfd/                # Compatibility imports for existing callers
├── models.py                      # Compatibility imports for domain models
├── optimizer.py                   # Genetic algorithm
├── parsec.py                      # Compatibility imports for 2D PARSEC math
├── mesh_study.py                  # Compatibility imports for 2D mesh studies
├── design_import.py               # Compatibility imports for 2D design loading
├── preview.py                     # Compatibility imports for 2D previews
├── storage.py                     # Project and optimization-state persistence
├── geometry_worker.py             # Legacy FreeCAD worker launcher
└── cfd_worker.py                  # Legacy Fluent/BEM worker launcher
resources/
└── workflows/
    ├── axisymmetric_2d/            # Ducted CAD, mesh, Fluent/UDF and BEM tables
    └── axisymmetric_2d_open_turbine/ # Open CAD, mesh, case, UDF and BEM tables
```

The **Project** tab selects a workflow. The selected ID is saved in
`opturbo_project.json`; older project files without an ID load as
`axisymmetric_2d`. `workflows/selection.py` is the small, explicit map used to
create that workflow's runner. Each workflow owns its geometry, CAD, meshing,
solver adapters, and resource-root choice. Every workflow loads its own files
from `resources/workflows/<workflow_id>/`; shared UDF and BEM-table assets are
copied into each workflow folder so one workflow can run without reading the
other workflow's resources. The recorded ducted SpaceClaim script keeps its
required handoff paths unchanged.
The project model also preserves per-workflow options in
`workflow_settings[workflow_id]` for later workflow-specific settings.

The original `opturbo.geometry`, `opturbo.cfd`, and
`opturbo.pipeline.runner` import paths remain as compatibility facades. New
workflow-specific code belongs below `opturbo.workflows/<workflow_id>/`.

### Repository folder map

```text
OpTurbo/
├── run.py                          # Start the desktop application
├── src/opturbo/                    # Application package; see its README
│   ├── gui/                        # Tkinter UI and PDF help links
│   ├── domain/                     # Settings models and validation
│   ├── pipeline/                   # Workflow-neutral process helpers
│   ├── workflows/                  # Workflow registry and implementations
│   │   └── axisymmetric_2d/         # Geometry, CFD/BEM, workers and pipeline
│   ├── geometry/, cfd/             # Legacy implementation facades
│   └── optimizer.py, storage.py    # Shared GA and persistence services
├── resources/                      # Vendor scripts, baseline and CFD tables
│   ├── spaceclaim/
│   ├── meshing/
│   ├── fluent/libudf/
│   └── cfd_tables/
├── scripts/                        # Documentation builder and dev runner
├── docs/                           # Manual/theory Markdown and PDFs
└── tests/                          # Standard-library unit tests
```

Each code/resource directory has a local `README.md` with its full immediate
file tree and a short purpose statement for every source file. Read the local
guide before editing that area; the package-level guides link the current
workflow boundaries and external resource dependencies.

## Verification

Unit tests and Python compilation can be run without launching the engineering
applications:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src run.py
```

An end-to-end evaluation requires working installations and valid licenses for
FreeCAD, SpaceClaim, ANSYS Workbench/Meshing, and Fluent.
