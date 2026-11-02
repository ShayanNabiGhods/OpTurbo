"""Open-turbine workflow backed by OpenFOAM running inside WSL."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .runner import OpenFoamOpenTurbineRunner


@dataclass(frozen=True)
class Axisymmetric2DOpenTurbineOpenFoamWorkflow:
    """Evaluate an open turbine with FreeCAD geometry and OpenFOAM/BEM."""

    application_root: Path

    workflow_id = "axisymmetric_2d_open_turbine_openfoam"
    title = "2D axisymmetric open turbine (OpenFOAM)"
    run_only = True

    @property
    def resources(self) -> Path:
        """Return the workflow's independent OpenFOAM and BEM resource folder."""
        return self.application_root / "resources" / "workflows" / self.workflow_id

    def create_runner(self, emit: Callable[[str], None] = print,
                      cancel: Callable[[], bool] | None = None) -> OpenFoamOpenTurbineRunner:
        """Create the candidate runner for individual and mesh-study evaluations."""
        return OpenFoamOpenTurbineRunner(self.application_root, emit=emit, cancel=cancel)
