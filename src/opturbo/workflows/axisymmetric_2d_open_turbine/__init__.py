"""Geometry-only workflow for an open 2D axisymmetric turbine."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .runner import OpenTurbineRunner


@dataclass(frozen=True)
class Axisymmetric2DOpenTurbineWorkflow:
    """Generate an open-turbine STEP handoff without CAD or CFD stages."""

    application_root: Path

    workflow_id = "axisymmetric_2d_open_turbine"
    title = "2D axisymmetric open turbine"
    geometry_only = True

    def create_runner(
        self,
        emit: Callable[[str], None] = print,
        cancel: Callable[[], bool] | None = None,
    ) -> OpenTurbineRunner:
        """Create the FreeCAD-only runner for this workflow."""
        return OpenTurbineRunner(self.application_root, emit=emit, cancel=cancel)
