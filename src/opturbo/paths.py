"""Stable paths to the installed application root and bundled resources."""

from pathlib import Path


APPLICATION_ROOT = Path(__file__).resolve().parents[2]
RESOURCES_ROOT = APPLICATION_ROOT / "resources"
