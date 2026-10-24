"""Shared reference to pipeline runtime settings for one tool stage."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runner import PipelineRunner


class PipelineStage:
    """Give a stage explicit access to paths and callbacks owned by the runner."""

    def __init__(self, runner: "PipelineRunner") -> None:
        self.runner = runner
