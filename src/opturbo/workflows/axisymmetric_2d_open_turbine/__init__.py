"""Manual-SpaceClaim open-turbine workflow through ANSYS meshing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .runner import OpenTurbineRunner


@dataclass(frozen=True)
class Axisymmetric2DOpenTurbineWorkflow:
    """Prepare open-turbine geometry and mesh before Fluent case setup."""

    application_root: Path

    workflow_id = "axisymmetric_2d_open_turbine"
    title = "2D axisymmetric open turbine"
    preparation_only = True

    def create_runner(
        self,
        emit: Callable[[str], None] = print,
        cancel: Callable[[], bool] | None = None,
    ) -> OpenTurbineRunner:
        """Create the open-turbine geometry and meshing runner."""
        return OpenTurbineRunner(self.application_root, emit=emit, cancel=cancel)
