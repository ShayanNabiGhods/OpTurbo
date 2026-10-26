# OpTurbo User Manual

**Build, evaluate, optimize, and review axisymmetric wind-turbine designs**
User guide for OpTurbo v0.3.2 - October 2026

This guide explains the controls in OpTurbo v0.3.2. The ducted workflow uses FreeCAD, SpaceClaim, ANSYS Meshing, and Fluent, with a blade-element/momentum (BEM) calculation coupled to Fluent and optional genetic optimization. The open-turbine workflow evaluates a duct-free design and retains mesh study, without optimization. A separate Simple BEM tab calculates rotor performance without running either CFD workflow. Engineering programs and valid licenses are required for a full CFD evaluation. Project setup, configuration, and the ducted geometry preview can be completed before those programs are installed.

## Start here {#start-here}

1. Install Windows Python 3.10 or newer with Tkinter, FreeCAD 1.1, and the ANSYS release used by your project. The default executable paths target ANSYS v242.
2. Open PowerShell in the project folder and run `python run.py`.
3. In **Project**, select the workflow, give the project a name, choose a results folder outside the source tree, and check all four executable paths.
4. For the ducted workflow, use **Design** to inspect the selected duct type and preview. The open-turbine workflow has no duct and hides this tab.
5. In **Workflow Settings**, check geometry, mesh, and CFD/BEM inputs. Save the project.
6. To use custom blade or airfoil data, import and save the headerless CSV files in **Aerodynamic Data**; check their units and dimensions against the formats in that chapter.
7. Use **Evaluate current design** once before starting the genetic algorithm, or use **Run performance evaluation** for an open turbine. Review the Monitor log if any stage fails.

The application validates configuration before launching expensive tools. Both workflows run geometry, SpaceClaim, meshing, and Fluent/BEM; only the ducted workflow supports genetic optimization. Candidates are saved independently so failures and successful results can be inspected later.

## Project tab {#project-settings}

### Engineering workflow

This branch registers `axisymmetric_2d` (ducted turbine) and `axisymmetric_2d_open_turbine` (open turbine). The workflow owns the geometry, solver adapters, and resource selection. The ducted workflow has a **Design** tab and genetic optimization. The open workflow hides **Design**, renames **Optimization** to **Run**, and supports a single performance evaluation plus mesh study. Projects store the workflow ID, so opening an older project without an ID falls back to `axisymmetric_2d`.

### Project name and Save folder

The name identifies the study. The selected folder is the durable results location. Choose a folder outside the source-code checkout. OpTurbo stores the project configuration, optimization history and state, logs, best result, candidate folders, and any mesh-study files there. Save the project after changing settings.

### Save now, New, Open, and Save As

Saving initializes or updates the project configuration. Open loads an `opturbo_project.json`; New clears the current project state in the interface; Save As selects another workflow folder. While work is running, project changes are blocked to keep the running candidate configuration consistent.

## External application paths {#tool-paths}

Set the executable path for each installed program:

- **FreeCAD executable** creates the candidate geometry and STEP exports.
- **SpaceClaim executable** opens the staged assembly using the supplied recorded script.
- **ANSYS Workbench executable** launches the candidate meshing journal.
- **Fluent executable** runs CFD and participates in the BEM coupling.
- **Fixed SpaceClaim handoff folder** is used by the ducted workflow. The recorded script requires `C:\OpTurbo\Temp Files\profile_assembly.step` and writes `C:\OpTurbo\Temp Files\profile_assembly.scdoc`. OpTurbo stages and collects those files for each candidate. The open workflow uses its packaged assembly script and candidate-local files.

Use Browse to select an executable. A path that points to the wrong release or a missing program will prevent that stage from starting. The SpaceClaim script depends on recorded body and face identities; substantial topology changes can invalidate it.

## Design tab: duct family and preview {#design-family}

The ducted workflow's Design tab supports two duct families. It is hidden in the open-turbine workflow, which has no duct-design variables:

- **airfoil** makes a closed PARSEC profile with upper and lower contours. Its chord and angle are shown as design variables alongside the upper/lower profile variables.
- **flanged** makes a lower PARSEC contour and a flange. Its chord, wall thickness, flange length and angle are shown with five lower-contour variables.

Switching families loads that family's own variable list. The preview has **Whole domain** and **Duct detail** views. The **Update preview** button refreshes the displayed profile after edits; numeric value changes also refresh the drawing. A design is checked for valid geometry before external tools start. Both families are exported as faces, not open wires.

### Design variable table {#design-variables}

Each row has **Use**, **Parameter**, **Minimum**, **Value**, and **Maximum**. Tick **Use** to let the optimizer vary that parameter. Unticked values stay fixed. The minimum and maximum define the allowed search interval; the current value is the starting/reference design and is used when the variable is fixed. Bounds must be ordered and the resulting profile must be geometrically valid. Start with a small number of active parameters and modest ranges.

**Select all** and **Clear all** change the optimization flags for the visible duct family. They do not expand or reduce bounds. When switching family, OpTurbo retains each family's last edited variable set in the open session.

**Load design** imports a saved design snapshot or settings JSON. Check the selected family and preview after loading. A loaded value is included in the available range if it lies outside the family's default bounds.

### PARSEC parameters {#parsec-parameters}

The airfoil family uses the upper and lower PARSEC parameters; the flanged family uses the five lower-surface parameters. A leading-edge radius controls nose roundness. Crest location is the chordwise location of maximum ordinate; crest height sets that ordinate relative to the profile reference line; crest curvature controls local curvature at the crest. Trailing-edge height and slope set the profile endpoint and direction. Values are normalized PARSEC shape values unless the label explicitly says degrees or millimetres. Keep each bound physically plausible and inspect the full profile for intersections or abrupt curvature.

The flanged-family geometry controls are **Duct chord**, **Duct wall thickness**, **Flange length**, and **Flange angle**. Its profile variables are **Crest location**, **Crest height**, **Crest curvature**, **Trailing-edge height**, and **Trailing-edge slope**. The airfoil-family geometry controls include **Duct angle of attack** and **Duct chord**.

## Workflow Settings: geometry {#geometry-settings}

Geometry controls describe the 2D meridional section in millimetres. Preview outlines help check placement; they do not replace geometry validation.

### Outer domain

**Domain length** and **Domain height** define the rectangular computational region. **Domain origin x** and **Domain origin r** place its lower-left/reference corner. The domain needs enough clearance upstream, downstream, and radially to avoid forcing the result with nearby boundaries.

### Resolution region

**Resolution-region length**, **Resolution inlet radius**, **Resolution origin x**, and **Resolution origin r** define the locally refined region around the rotor and duct. This focuses mesh cells where gradients and the actuator-disk interaction matter. Keep the region inside the outer domain and surrounding the important flow area.

### Actuator disk

**Actuator radial span**, **Actuator thickness**, and **Actuator origin x** define the finite-thickness axisymmetric zone where BEM blade loads are applied to the CFD solution. Match its span and axial position to the rotor represented by the CFD mesh and BEM inputs.

### Hub and duct placement

**Hub length**, **Hub radius**, **Hub origin x**, and **Hub origin r** place the centre-body hub. **Duct origin x** and **Duct origin r** place the duct profile. These settings are in millimetres and should be consistent with the rotor and actuator disk. **Duct spline points** controls profile sampling: more points can describe the curve more smoothly, with additional geometry/mesh cost. Profile reversal is an implementation-level orientation option; change it only when the profile orientation requires it.

## Workflow Settings: meshing {#mesh-settings}

Mesh sizes and thicknesses are in centimetres; the curvature limit is in degrees.

- **Global element size** controls the background mesh away from refinements.
- **Resolution-region size** sets a target inside the refined flow region.
- **Duct-wall size** and **Hub-wall size** refine the solid boundaries. Duct-wall sizing is hidden for the open-turbine workflow, which has no duct.
- **Growth rate** controls the increase in cell size between nearby zones. Values must be greater than 1; gradual growth generally avoids abrupt transitions.
- **Curvature angle** asks the mesher for finer sampling of curved geometry at smaller angle limits.
- **CPU cores for parallel part meshing** can be **Program Controlled** or an explicit count. This is an ANSYS Meshing setting, not the Fluent processor count.
- **Meshing method** supports **Default (ANSYS automatic)**, **Quad**, **Tri**, and **MultiZone**. Default leaves method choice to ANSYS. Explicit choices apply a method control to the whole-domain body and may not suit every geometry.
- **Add inflation layers** enables boundary-layer cells on hub and duct walls. **Inflation layers** sets the number of layers; **Inflation max thickness** sets their maximum total thickness. The latter controls total layer thickness, not each individual layer. These dependent fields are disabled when inflation is off.

Smaller sizes and more refinement can improve spatial resolution but increase memory and run time. Compare results with a mesh study before interpreting small performance differences.

## Mesh Study tab {#mesh-study}

Mesh Study holds the design fixed and compares mesh configurations. Geometry and CFD/BEM inputs come from Workflow Settings; values in the Mesh Study panel define the mesh candidates.

### Candidate controls

Choose a **Mesh method** and **CPU cores** as in Workflow Settings. For each mesh-size variable, tick its checkbox to include it in the sweep. The **Minimum**, **Current**, and **Maximum** values define a sweep interval and reference mesh setting. Size variables cover global, growth, curvature, resolution, duct (ducted workflow only), hub, and—when inflation is enabled—inflation controls. Disabled rows are ignored. Inflation settings are not swept when inflation is disabled.

**Automatic sweep cases** must be between 1 and 100. The application uses only an evenly spaced sweep: each enabled value moves together from its minimum to its maximum across the requested cases. A one-case sweep uses the midpoint of each enabled range; integer inflation-layer counts round upward. This is a finite candidate plan, not proof that the mesh is fully converged.

**Run this mesh setup** evaluates one panel configuration. **Run automatic mesh sweep** evaluates the planned cases. **Load mesh values from Workflow Settings** copies the main meshing settings into this panel. **Resume mesh study** continues a saved unfinished study and reuses completed cases. **Stop after current case** lets the current evaluation finish; **Terminate whole process** ends the active process. Termination can leave a candidate incomplete.

### Review table

The table lists candidate status, cell count, meshing time, Fluent/BEM time, total time, outer iterations, Cp/Ct, and duct-tip-normalized Cp/Ct. Select a row to see its exact mesh settings, candidate directory, and any error. **Copy selected mesh settings to Workflow / Meshing** copies the selected setup back to the main meshing form; save the project to retain it.

Mesh studies write `mesh_study/settings.json`, `history.json`, `run_state.json`, and their candidate artifacts below the project folder. A mesh study evaluates full candidates, so each case includes Fluent/BEM work, not only meshing.

## Workflow Settings: flow and rotor {#flow-inputs}

Fluent and BEM share the operating-point inputs. Use SI units here:

- **Free-stream speed**: inlet wind speed in m/s.
- **Air density**: kg/m3; **Dynamic viscosity**: Pa s. These set fluid properties.
- **Rotor radius** and **Rotor hub radius**: metres. These define the BEM blade span.
- **Blade count**: number of blades represented by the actuator-disk model.
- **Rotor angular speed**: rad/s; **Blade pitch**: degrees.
- **BEM radial stations**: number of discrete stations spanning hub to tip. More stations resolve radial variation more finely and require more calculation.

The CFD geometry and BEM rotor dimensions must describe the same rotor. Use the **Aerodynamic Data** tab to edit or replace the active workflow's blade geometry and airfoil performance tables.

## Simple BEM tab {#simple-bem}

The **Simple BEM** tab calculates a rotor performance curve without creating a duct/domain, meshing, or starting Fluent. It uses the flow speed, density, viscosity, rotor radius, hub radius, blade count, pitch, and radial-station count currently shown in **Workflow Settings → CFD / BEM**. Unsaved edits are used immediately. The calculation uses the active workflow's blade geometry and airfoil polar tables. Blade radius, chord, and twist are used as stored in the geometry CSV; they are not silently scaled. Set rotor and hub radii so the imported blade span lies within them.

Set **Minimum TSR**, **Maximum TSR**, and **TSR interval**. The sweep includes values reached by repeatedly adding the interval while the result remains at or below the maximum, with a limit of 101 points per run. For example, 4 to 8 in steps of 0.5 evaluates 4, 4.5, …, 8. Rotor speed is calculated for each point from `omega = TSR * free-stream speed / rotor radius`.

Choose **Prandtl** or **Bontempo 2025** for tip loss. Prandtl is the default and applies conventional tip and root loss. Bontempo applies its empirical tip correction with Prandtl root loss; its coefficients remain the values configured in Workflow Settings. Bontempo is a duct-calibrated correction and may not be appropriate for an unducted rotor.

The **Results table** reports angular speed, power, Cp, Ct, and the number of radial stations whose induction iteration converged. The **Cp / Ct plot** sub-tab plots both coefficients against the actual TSR values from the sweep. A point can finish with some unconverged stations; review that count before using its performance values. These results are a reduced-order estimate from the active workflow's blade/polar data, not a CFD result or turbine certification.

## Aerodynamic Data tab: edit and import CSV tables {#aerodynamic-data}

The **Aerodynamic Data** tab edits the blade geometry and airfoil polar inputs used by both ducted and open-turbine CFD/BEM runs and by **Simple BEM**. Select a CSV in the **Datasets** list; its row count and filename appear beside the table. The format note describes the selected file. The Reynolds-number row uses sequential **Re 1**, **Re 2**, … headings; lift and drag matrices use sequential **Values 1**, **Values 2**, … headings. These are editor headings only and are not written into the headerless CSV. Double-click a displayed cell to edit its numeric value. Use **Import CSV…** to load a replacement file into the selected table; its layout is checked before it is staged. Unsaved datasets are marked with an asterisk. Use **Save tables** to validate the complete related set and write the staged files. **Discard edits** reloads the saved files. Leaving the tab does not save changes automatically. When changing workflows with staged edits, choose whether to save them to the current workflow before switching.

Each workflow has a separate copy under `resources/workflows/<workflow-id>/cfd_tables/`. A save changes only the selected workflow's tables; past candidate results remain as they were. New evaluations and Simple BEM runs use the currently selected workflow's saved tables.

All files use comma-separated decimal numbers, UTF-8 text, and **no header row**. Blank lines are ignored. The required formats are:

- **`ntnu_geometry.csv`**: one blade section per row, exactly three columns in this order: `radius_m, chord_m, twist_deg`. Use at least two sections, positive radius and chord, and strictly increasing radii from hub to tip. Any section count is accepted. For example, `0.0525,0.0495,38` is one row. The CFD/BEM radial-station setting determines the calculation count. If that count matches the imported rows, the stations are preserved; otherwise radius, chord, and twist are linearly interpolated onto evenly spaced stations.
- **`s826_alpha.csv`**: one angle-of-attack value in degrees per row, strictly increasing. Example rows: `-10` then `-8`.
- **`s826_re.csv`**: one row containing at least two positive, strictly increasing Reynolds numbers. Example: `50000,70000,100000`.
- **`s826_cl.csv`** and **`s826_cd.csv`**: numeric matrices with one row per angle in `s826_alpha.csv`, and one column per Reynolds number in `s826_re.csv`. The first row of each matrix belongs to the first angle; the first column belongs to the first Reynolds number. Both matrices must have exactly matching dimensions. Lift values may be positive or negative; drag values must be zero or positive.

For a complete custom polar set, import matching alpha, Reynolds, lift, and drag files in any order, then save the set. Saving rejects incomplete or mismatched dimensions, nonnumeric/non-finite values, unordered axes, duplicate axis values, and invalid geometry. The same airfoil polar table is used at every radial blade section; the geometry CSV supplies section-wise radius, chord, and twist.

## BEM loss correction {#bem-model}

**Tip-loss correction** selects **Prandtl** or **Bontempo 2025**. Prandtl includes conventional tip and root loss. Bontempo replaces the tip factor with the duct-specific empirical correction and multiplies it by the Prandtl root-loss factor, so root loss remains active. It is a calibration choice and may not suit every duct or operating regime.

With Bontempo selected, **A**, **B**, and **C** control the empirical expression `g = exp(A * (blade count * tip-speed ratio - B)) + C`. Defaults are A = -0.229, B = 22.0116, and C = 0.4427. The tip-speed ratio is rotor tip speed divided by free-stream speed. Keep the calibrated defaults unless using a documented alternative calibration. The coefficients are disabled with Prandtl selected.

## CFD/BEM coupling controls {#solver-coupling}

- **Maximum outer iterations** limits alternating BEM and Fluent updates.
- **Fluent iterations per outer iteration** sets the inner CFD solve work.
- **Tolerance** is the required change in coupled Cp/Ct before the coupling is considered converged.
- **Relaxation** is the fraction of a new source update applied each coupling step, from 0 to 1. Lower values damp changes but can slow convergence.
- **Fluent processors** sets parallel solver processes. This is separate from mesh CPU cores.
- **Keep iteration data** retains intermediate Fluent data files, increasing storage use.
- In the ducted workflow, **Source initialization** is **Conservative** or **Previous candidate**. Conservative uses the generated starting source field. Previous candidate reuses the last successfully completed candidate's final relaxed actuator-disk sources; the first candidate falls back to conservative initialization.
- **Previous-source weight** blends old and new starting sources: 0 is fully conservative, 1 uses fully previous sources. This control is active only in previous-candidate mode. The open-turbine workflow hides both source-initialization controls and always uses conservative initialization.

The genetic algorithm can prepare one next candidate through meshing while the current candidate runs Fluent by enabling **Overlap meshing with Fluent (experimental)**. It is limited to one generation, consumes additional memory, and may require concurrent ANSYS licenses. The next Fluent run waits for its mesh to finish.

## Fluent model and numerical controls {#fluent-settings}

### Turbulence model and residual criteria

Choose **k-omega standard**, **k-epsilon standard**, or **Spalart-Allmaras**. The model controls which equation residuals and discretization controls are used. Continuity and axial, radial, and swirl-velocity residuals apply to all. The `k` residual applies to k-omega and k-epsilon; `epsilon` applies to k-epsilon; `omega` applies to k-omega; `nut` applies to Spalart-Allmaras. Residual criteria are convergence thresholds, not direct accuracy guarantees.

### Discretization and pressure-velocity coupling

**Pressure interpolation**, **Momentum discretization**, **Swirl discretization**, and **Pressure-velocity coupling** select the corresponding Fluent schemes at the first solver setup. The model-specific `k`, `epsilon`, `omega`, and turbulent-viscosity (`nut`) discretization fields apply only when their equation is active. Scheme names are Fluent choices; higher-order schemes may need a better initial field or more iterations to converge. These settings configure the supplied journal and should be changed with solver expertise.

## Optimization / Run tab {#optimization-controls}

### Objective and genetic algorithm

This tab is called **Run** for the open-turbine workflow; it offers a single evaluation and does not show optimization controls. For ducted designs, **Optimization criterion** chooses Cp, Ct, Cp normalized by duct-tip area, or Ct normalized by duct-tip area. The selected value is fitness to maximize. Duct-tip normalization uses the maximum radius of the candidate geometry; it changes the metric and may change which candidate ranks highest.

- **Population size** is the number of candidates per generation.
- **Generations** is the number of generations to evaluate.
- **Elite designs retained** copies top candidates unchanged into the next generation.
- **Tournament size** sets how many candidates compete when a parent is selected.
- **Crossover probability** controls how often a child combines two parents.
- **Mutation probability** controls how often an individual design variable is perturbed.
- **Mutation scale** is mutation standard deviation as a fraction of that variable's range.
- **Random seed** fixes the pseudo-random sequence for repeatable search decisions.
- **Overlap meshing with Fluent** enables the experimental preparation mode described above.

Real-valued variables use tournament selection, arithmetic crossover, Gaussian mutation, bound clamping, and elitism. A fixed seed helps reproduce the algorithm sequence, but small numerical differences between engineering-software runs may still occur. A modest population and few generations are suitable for a setup check; useful optimization usually requires a larger budget and validated models.

### Run controls

**Evaluate current design** runs the current geometry once, without population search. Use it to check the end-to-end setup. **Start GA optimization** begins a new optimization. **Resume previous optimization** continues a saved run when its workflow settings match. Completed candidates are reused and candidates without saved results are evaluated again. **Stop after current candidate** allows in-flight work to finish. **Terminate whole process** requests whole-process termination and can leave incomplete artifacts.

The progress bar counts candidate evaluations. The result table shows evaluation, generation, candidate, Cp, Ct, normalized values, and status. The best-result line identifies the best candidate for the active objective.

## Monitor tab {#monitor}

The log shows pipeline stages and Fluent output. In the ducted workflow, **Candidates** plots performance histories. The open-turbine workflow hides this history view because its results are shown in the Run panel. **BEM** shows the latest axial/tangential induction and loss-factor distributions by radial station. **Live residuals** plots residual history on a logarithmic scale as Fluent reports it. **Outer Cp / Ct** shows the coupled performance values across outer iterations. A flat trace alone does not establish mesh or model independence; review logs and candidate artifacts as well.

## Accessibility tab {#accessibility}

The display controls change the interface immediately and are saved with the project. **Theme** selects light or dark appearance. **Text size** scales interface fonts. **High contrast** uses a black background and bright foreground/focus colors. **Accent color** changes selected tabs, primary buttons, and progress. **Candidate marker size** and **Outer Cp / Ct marker size** set plot markers. **Table row spacing** adds vertical pixels to table rows. Use Tab/Shift+Tab to move between controls, Space to toggle a focused checkbox, and Enter to activate a focused button. The **Help** button in the top bar opens this manual.

## Candidate pipeline and saved files {#candidate-results}

Each evaluation receives a new sequential candidate folder. The ducted workflow's four stages are:

1. **Geometry**: FreeCAD creates the domain, hub, actuator disk, and duct faces; STEP files and inputs are saved.
2. **SpaceClaim**: the supplied recorded script imports the staged geometry and saves its document.
3. **Meshing**: a candidate-specific Workbench journal and mesh script create `axisymmetric_mesh.msh`.
4. **Fluent/BEM**: the baseline case loads the mesh; Fluent and BEM alternate source updates until convergence or the iteration limit. Reports and result files are retained.

The open-turbine workflow uses the same four candidate stages, but its geometry contains no duct, its packaged SpaceClaim and Fluent resources are used, and its **Design** tab and optimization controls are absent.

The project folder includes `opturbo_project.json`, optimization history and state, `best/`, `logs/`, `exports/`, `candidates/`, and (when used) `mesh_study/`. A candidate normally contains `candidate.json`, a `result.json` or `failure.json`, and `01_geometry/`, `02_spaceclaim/`, `03_mesh/`, and `04_cfd/` subfolders. Candidate directories preserve configuration, inputs, outputs, logs, and summaries when available. Failed candidates retain diagnostics and receive low fitness so search can continue.

## Resume, stopping, and recovery {#recovery}

Save the project before long runs. Resume from the project folder that contains the saved optimization state. Resume requires the workflow settings to match the saved run; restore those settings if the application reports a mismatch. Mesh studies have their own resume state and reuse completed cases.

Use **Stop after current candidate/case** for a safe pause between evaluations. Active Fluent work and active overlap preparation are allowed to finish. Use whole-process termination only when necessary; a killed external program may leave a failed or incomplete candidate. Inspect that candidate's `failure.json`, stage logs, and last completed stage before retrying. A retry creates a new candidate directory rather than replacing previous results.

## Troubleshooting {#troubleshooting}

- **External program does not start**: check executable paths, installation, release compatibility, working permissions, and license availability.
- **SpaceClaim import or script error**: check the handoff path and verify that the recorded geometry body/face selections still match the topology.
- **Geometry rejected**: check PARSEC bounds, self-intersection, family-specific values, duct/hub placement, and domain extents. Reduce the variable range and preview again.
- **Meshing failure**: inspect the mesh-stage log; check method compatibility, geometry validity, inflation thickness, and whether local sizes are too small for the domain.
- **Fluent does not converge**: inspect residual and outer-iteration plots, increase iteration budgets cautiously, try conservative source initialization, and verify SI units and geometry/rotor consistency.
- **Resume rejected**: reload the original settings saved with the run. Do not edit the candidate record to bypass configuration matching.
- **Unexpected performance ranking**: verify the selected objective and normalization, compare mesh sensitivity, inspect BEM loss factors, and examine the saved candidate settings and reports.

## Units and safe starting practice {#units-reference}

Geometry is entered in **millimetres**. Mesh sizes and inflation thickness are in **centimetres**. CFD/BEM operating inputs use **metres, seconds, kilograms, pascals, and radians** as named by each control; pitch and profile angles are in **degrees**. Convert carefully when comparing geometry with rotor dimensions.

Keep a baseline project. Evaluate it once before optimization, then change one group of assumptions at a time. Validate the mesh independently, record turbulence and loss-correction assumptions, and compare candidates at the same physical operating point. Optimization searches the configured model and bounds; it does not establish that those assumptions represent a real turbine.
