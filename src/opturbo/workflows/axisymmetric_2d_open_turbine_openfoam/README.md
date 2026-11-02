# 2D axisymmetric open turbine with OpenFOAM

This run-only workflow uses FreeCAD for the open-turbine geometry, OpenFOAM in
WSL for meshing and CFD, and OpTurbo's existing BEM implementation for the
actuator-disk coupling. The existing `axisymmetric_2d_open_turbine` workflow
remains available separately and continues to use SpaceClaim, ANSYS Meshing,
and Fluent.

## Setup

Select **2D axisymmetric open turbine (OpenFOAM)** on the Project tab. Configure
the FreeCAD command-line executable and these WSL/OpenFOAM fields:

- **WSL executable**: normally `C:\Windows\System32\wsl.exe`.
- **WSL distribution**: the exact name shown by `wsl.exe --list --quiet`.
- **OpenFOAM environment script**: an absolute Linux path sourced before each
  utility call. This computer's Foundation 14 install uses
  `/opt/openfoam14/etc/bashrc`.
- **WSL Windows-drive mount root**: `/mnt` for the standard Ubuntu WSL layout.
- **OpenFOAM scratch folder**: an absolute Linux path without spaces, such as
  `/tmp/opturbo-openfoam` or `/home/<user>/opturbo-openfoam`.

The WSL account must be able to source the OpenFOAM script, read the project's
Windows-drive mount, and write to the scratch folder. OpTurbo stages each case
on that WSL Linux filesystem so OpenFOAM does not receive a Windows project
path containing spaces. Every utility runs in the selected distribution after
the configured environment script is sourced.

The WSL installation verified for this workflow is Ubuntu 24 with OpenFOAM
Foundation 14. Other distributions and OpenFOAM releases have not been
verified; their dictionary layouts or utility behavior may differ.

## Pipeline and results

1. **FreeCAD geometry** exports the STEP assembly, a metre-scaled hub STL, and
   the hub's sampled meridional profile in `openfoam_hub_profile.json`.
2. **OpenFOAM meshing** builds a body-fitted, five-degree wedge mesh with
   `blockMesh` using that FreeCAD profile. `surfaceCheck` checks the exported
   STL, `checkMesh` must report a valid mesh, and `topoSet` creates one annular
   cell zone for each BEM radial station. The small centerline core is clipped
   to avoid zero-area wedge cells; its radius is recorded in `mesh_info.json`.
3. **OpenFOAM CFD/BEM coupling** runs `simpleFoam`, samples axial and
   circumferential velocity at the BEM stations, solves OpTurbo's existing BEM
   model, relaxes the actuator momentum sources, and updates `fvModels` for the
   next outer iteration. The run stops at the configured Cp/Ct tolerance or
   outer-iteration limit.

The Run panel supports one performance evaluation and an evenly spaced TSR
sweep. Mesh Study varies the active global, resolution-region, and hub sizes.
Candidate folders contain the FreeCAD files, mesh and solver logs, OpenFOAM
case, iteration history, BEM sources, and final `result.json` or `failure.json`:

```text
candidate_001/
├── candidate.json
├── preparation.json
├── result.json                 # or failure.json
├── 01_geometry/                # STEP, STL, and profile JSON
├── 02_mesh/
│   ├── meshing.log
│   ├── mesh_info.json
│   └── openfoam_case/          # dictionaries, polyMesh, and fields
└── 03_cfd/
    ├── openfoam_driver.log
    ├── iteration_history/
    ├── final_ad_sources.dat
    └── resources/              # candidate-local BEM tables
```

The workflow is run-only: Design and genetic-optimization controls are hidden.
It reuses the existing flow/rotor, BEM station, coupling iteration,
convergence, and source-relaxation settings. OpenFOAM settings expose the
maximum block-mesh cell count, linear-solver tolerance, equation relaxation,
inlet turbulence intensity, and wedge angle. Fluent processor controls and
ANSYS mesh controls are hidden; OpenFOAM runs in one process.

Successful runs copy the complete case back into the project candidate and
remove their WSL scratch copy. Failed runs record the failing stage and scratch
path in `failure.json`, leaving the WSL case available for diagnosis.
