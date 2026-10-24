"""Helpers for reading and comparing saved project settings."""

from ..models import ProjectConfig


def saved_configuration_matches(saved: object, requested: ProjectConfig) -> bool:
    """Compare snapshots after filling defaults for settings added in newer versions."""
    if not isinstance(saved, dict):
        return False
    try:
        normalized = ProjectConfig.from_dict(saved).to_dict()
    except (TypeError, ValueError):
        return False
    return normalized == requested.to_dict()
