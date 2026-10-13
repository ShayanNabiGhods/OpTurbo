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

Tkinter is included with the standard Windows Python installer. Check the
executable paths on the **Project** tab before running. The default paths are
configured for FreeCAD 1.1 and ANSYS 2024 R2 (`v242`). Choose a workflow save
folder outside the source-code folder, for example
`C:\OpTurbo\Projects\baseline-study`.

## Application workflow

- **Project** — set the project name, results folder, and external application
  paths.
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

The tip-loss choices are Prandtl and Bontempo. Prandtl is the default. The
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
├── app.py                 # Tkinter interface and run coordination
├── models.py              # project, design, mesh, CFD, and GA settings
├── optimizer.py           # genetic algorithm
├── parsec.py              # design validation and preview mathematics
├── storage.py             # project and optimization-state persistence
├── geometry/              # FreeCAD geometry generation
├── cfd/                   # CFD/BEM coupling
└── pipeline/              # external-process and candidate workflow
resources/
├── spaceclaim/            # recorded SpaceClaim script
├── meshing/               # ANSYS Meshing script and artifact extractor
├── fluent/                # baseline case and UDF resources
└── cfd_tables/            # blade, airfoil, and operating-point data
```

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
