# OpTurbo

OpTurbo is a Windows desktop application for designing and optimizing ducted
wind turbines. It connects a Tkinter interface and genetic algorithm to a
four-stage engineering workflow: FreeCAD geometry, SpaceClaim, ANSYS Meshing,
and Fluent/BEM. The optimization objective is the final power coefficient
(`Cp`); thrust coefficient (`Ct`) and BEM distributions are also recorded.

## Start the application

Use Windows Python 3.10 or newer:

```powershell
cd "C:\Project Saves\Python Codes\OpTurbo"
python run.py
```

## Documentation

The **Help** button at the top of the application opens the complete
[User Manual](docs/manual.pdf). The **Help** menu also contains the
[Theory Guide](docs/theory.pdf). The Markdown sources are in `docs/`; regenerate
both PDFs with `python scripts/build_documentation.py`.

Tkinter is included with the standard Windows Python installer. Check the
executable paths on the **Project** tab before running. The default paths are
configured for FreeCAD 1.1 and ANSYS `v241`, matching the defaults in the
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
- **Optimization** — evaluate the current design, configure and start the
  genetic algorithm, resume a saved run, and review candidate results. A run
  can be stopped safely; active Fluent work and any active overlap preparation
  are allowed to finish.
- **Monitor** — review candidate results, BEM distributions, live residuals,
  and outer-iteration `Cp`/`Ct` plots in separate views.

## Candidate pipeline

Each candidate passes through these stages:

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
candidate's artifacts.

## Source layout

```text
run.py
src/opturbo/
├── app.py                         # Public GUI entry point and compatibility exports
├── gui/                           # Window, settings forms, design previews, result views
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
├── pipeline/                      # Shared process and optimization-pipeline helpers
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
├── spaceclaim/                    # Current workflow's recorded SpaceClaim script
├── meshing/                       # Current workflow's ANSYS scripts
├── fluent/                        # Baseline case and UDF resources
└── cfd_tables/                    # Blade, airfoil, and operating-point data
```

The **Project** tab selects a workflow. The selected ID is saved in
`opturbo_project.json`; older project files without an ID load as
`axisymmetric_2d`. `workflows/selection.py` is the small, explicit map used to
create that workflow's runner. Each workflow owns its geometry, CAD, meshing,
solver adapters, and resource-root choice. The existing 2D resources remain at
their established `resources/` paths because the recorded SpaceClaim script and
external tooling depend on those paths. New workflows can keep their assets in
`resources/workflows/<workflow_id>/` and select that directory in their own
workflow definition.
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
