"""Small explicit map from saved workflow identifiers to implementations."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .axisymmetric_2d import Axisymmetric2DWorkflow

if TYPE_CHECKING:
    from .axisymmetric_2d.pipeline import PipelineRunner


class Workflow(Protocol):
    """Common runner factory exposed by each workflow implementation."""

    title: str

    def create_runner(
        self,
        emit: Callable[[str], None] = print,
        cancel: Callable[[], bool] | None = None,
    ) -> "PipelineRunner":
        """Create the runner responsible for this workflow's candidate stages."""


_WORKFLOW_TYPES: dict[str, Callable[[Path], Workflow]] = {
    Axisymmetric2DWorkflow.workflow_id: Axisymmetric2DWorkflow,
}


def available_workflows() -> tuple[str, ...]:
    """Return the workflow IDs supported by this application version."""
    return tuple(_WORKFLOW_TYPES)


def get_workflow(workflow_id: str, application_root: Path) -> Workflow:
    """Create a workflow by its saved ID or raise an actionable error."""
    try:
        workflow_type = _WORKFLOW_TYPES[workflow_id]
    except KeyError as error:
        supported = ", ".join(available_workflows())
        raise ValueError(
            f"Unsupported workflow {workflow_id!r}. Available workflows: {supported}."
        ) from error
    return workflow_type(Path(application_root))
