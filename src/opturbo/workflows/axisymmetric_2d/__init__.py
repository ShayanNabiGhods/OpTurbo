"""Workflow definition for the existing two-dimensional axisymmetric model."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .pipeline import PipelineRunner


@dataclass(frozen=True)
class Axisymmetric2DWorkflow:
    """Select the CAD, meshing, solver, and resources used by this workflow."""

    application_root: Path

    workflow_id = "axisymmetric_2d"
    title = "2D axisymmetric ducted turbine"

    @property
    def resources(self) -> Path:
        """Return the resources packaged specifically for the ducted workflow."""
        return self.application_root / "resources" / "workflows" / self.workflow_id

    def create_runner(
        self,
        emit: Callable[[str], None] = print,
        cancel: Callable[[], bool] | None = None,
    ) -> "PipelineRunner":
        """Build the workflow runner with its own resource root."""
        from .pipeline import PipelineRunner

        return PipelineRunner(
            self.application_root,
            emit=emit,
            cancel=cancel,
            resources=self.resources,
        )
