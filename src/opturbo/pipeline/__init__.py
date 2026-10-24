"""Shared pipeline helpers and legacy runner import."""

__all__ = ["PipelineRunner"]


def __getattr__(name: str):
    """Load the legacy runner only when requested to avoid package cycles."""
    if name == "PipelineRunner":
        from .runner import PipelineRunner

        return PipelineRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
