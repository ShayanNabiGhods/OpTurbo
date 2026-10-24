"""Data returned by the geometry, CAD, and meshing preparation stages."""

from dataclasses import dataclass
from pathlib import Path

from ....models import ProjectConfig


@dataclass
class PreparedCandidate:
    """Candidate-owned inputs retained after the shared CAD/meshing stages."""

    config: ProjectConfig
    folder: Path
    mesh: Path
