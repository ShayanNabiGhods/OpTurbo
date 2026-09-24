# OpTurbo V0.0.1

OpTurbo is a beginner-readable Tkinter desktop application that connects the
existing DAWT geometry, SpaceClaim, ANSYS Meshing, Fluent, and BEM programs to
a genetic algorithm. Its objective is to maximize the final power coefficient
`Cp` by changing whichever duct angle, chord, and PARSEC variables the user selects.

The original four source folders remain unchanged outside this project. Their
capabilities are integrated as one standalone application: Python engineering
modules live under `src/opturbo/`, while SpaceClaim, meshing, Fluent, UDF, and
table assets live under `resources/`.

## Start the application

Use Windows Python 3.10 or newer because FreeCAD, SpaceClaim, Workbench, and
Fluent are Windows programs in the supplied setup:

```powershell
cd "C:\Project Saves\Python Codes\Complete Code - Copy\OpTurbo V0.0.1"
python run.py
```

Tkinter is included with the standard Windows Python installer. OpTurbo itself
has no third-party Python dependencies.

Before the first run, check the executable paths on the **Project** tab. The
defaults match FreeCAD 1.1 and ANSYS 2024 R2 (`v242`). Then choose a workflow
save folder. Do not choose the source-code folder; use a separate results
folder such as `C:\OpTurbo\Projects\baseline-study`.

## Application layout

- **Project** — a compact two-column layout for project storage and executable paths.
- **Design** — selectable duct angle of attack, chord length, and PARSEC values,
  with exact FreeCAD-derived domain outlines and a zoomed duct view. Unticked
  variables are visibly disabled. During a run, both views follow the candidate.
- **Workflow Settings** — geometry, mesh, and CFD/BEM controls combined into one
  two-column page. SpaceClaim remains protected and is intentionally not editable.
- **Optimization** — single-design evaluation, GA controls, progress, and the
  ranked stream of Cp/Ct results.
- **Monitor** — live pipeline/Fluent output on the left, with Cp/Ct history and
  radial `a`, `a'`, and Prandtl-loss plots stacked on the right.

## Four-stage candidate pipeline

1. **FreeCAD geometry** receives domain settings and the candidate PARSEC
   dictionary. It writes the five individual STEP files and
   `profile_assembly.step` into the candidate result folder.
2. **SpaceClaim** is not rewritten or parameterized. OpTurbo copies the
   assembly to the exact path expected by the recorded script:
   `C:\OpTurbo\Temp Files\profile_assembly.step`. The original script writes
   `profile_assembly.scdoc` beside it, and OpTurbo copies that document back to
   the candidate folder.
3. **ANSYS Meshing** receives a candidate-specific Workbench journal and a
   copy of the original named-selection/mesh script with only the exposed mesh
   values substituted. Workbench uses the short staging folder
   `C:\OpTurbo\Temp Files\Meshing` and exports `axisymmetric_mesh.msh` back to
   the candidate folder.
4. **Fluent/BEM** copies the baseline case and UDF resources into the candidate
   folder. The first Fluent journal reads the baseline case and executes
   `/mesh/replace "axisymmetric_mesh.msh"`. Every outer iteration saves Fluent
   output and BEM arrays. When **Keep every outer-iteration solution data
   file** is enabled, each `coupled_solution_N.dat.h5` is retained. The final
   `Cp` is the GA fitness; `Ct` and the BEM distributions are retained for
   monitoring.

The SpaceClaim script relies on recorded body/face identities. A geometry that
changes topology enough to invalidate those identities will fail safely and
receive a poor GA fitness. Its log and `failure.json` remain in the candidate
folder for diagnosis.

## Genetic algorithm

The implementation uses real-valued genes, a baseline individual, random
initial candidates, tournament selection, arithmetic crossover, Gaussian
mutation, bounds clamping, and elitism. A fixed random seed makes a run
repeatable. Failed geometry/mesh/CFD candidates receive a large negative
fitness so the rest of the population can continue.

Because every CFD evaluation is expensive, begin with a small population and
one or two generations. Evaluate the current design once before starting a GA
to verify the complete external-tool installation.

## Saved workflow structure

```text
chosen-project-folder/
├── opturbo_project.json          # editable settings; atomically saved
├── optimization_history.json     # every completed candidate
├── best/best_result.json         # current best design and artifact path
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

Existing candidate folders are never overwritten. Re-evaluating the same
generation/candidate creates a `_run02`, `_run03`, and so on.

## Source structure

```text
src/opturbo/
├── app.py                 # Tkinter GUI and background coordination
├── geometry/              # native FreeCAD geometry implementation
├── geometry_worker.py     # isolated FreeCAD command-line entry point
├── cfd/                   # native CFD/BEM coupling implementation
├── cfd_worker.py          # isolated Fluent/BEM command-line entry point
├── models.py              # all editable settings and variable definitions
├── optimizer.py           # independent genetic algorithm
├── parsec.py              # preview and design validation mathematics
├── storage.py             # atomic project/history persistence
└── pipeline/
    ├── process.py         # subprocess and path helpers
    └── runner.py          # adapters for the four engineering stages

resources/
├── spaceclaim/            # protected recorded SpaceClaim script
├── meshing/               # ANSYS mesh script and artifact extractor
├── fluent/                # baseline case and compiled/source UDF
└── cfd_tables/             # blade, airfoil, and operating-point data
```

`AGENTS.md` contains mandatory maintenance rules for future coding agents.

## Verification

The fast tests do not launch engineering software:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src run.py
```

A complete integration test requires valid local licenses and installations
of FreeCAD, SpaceClaim, Workbench/Meshing, and Fluent. Use **Evaluate current
design** for that test before committing a long optimization run.

V0.0.1 also includes a conservative three-candidate validation optimization:

```powershell
python scripts\run_small_optimization.py
```

It changes only duct angle of attack, upper crest location, upper crest
height, and lower crest height. The default two generations, population of
two, two CFD outer iterations, and 20 Fluent iterations are intended to test
the complete system rather than produce a converged engineering optimum.
