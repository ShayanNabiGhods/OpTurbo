"""Open-turbine run and performance-evaluation workflow."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .runner import OpenTurbineRunner


@dataclass(frozen=True)
class Axisymmetric2DOpenTurbineWorkflow:
    """Run an open-turbine candidate through Fluent/BEM without optimization."""

    application_root: Path

    workflow_id = "axisymmetric_2d_open_turbine"
    title = "2D axisymmetric open turbine"
    run_only = True

    @property
    def resources(self) -> Path:
        """Return the open-turbine workflow's self-contained resource directory."""
        return self.application_root / "resources" / "workflows" / self.workflow_id

    def create_runner(
        self,
        emit: Callable[[str], None] = print,
        cancel: Callable[[], bool] | None = None,
    ) -> OpenTurbineRunner:
        """Create the open-turbine candidate runner and mesh-study methods."""
        return OpenTurbineRunner(self.application_root, emit=emit, cancel=cancel)
