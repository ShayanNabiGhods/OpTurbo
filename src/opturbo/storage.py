"""Reliable project and candidate result saving."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ProjectConfig


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON through a temporary file so interrupted saves stay valid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


class ProjectStore:
    """Manage one user-selected workflow folder without overwriting results."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def initialize(self, config: ProjectConfig) -> None:
        """Create the standard project layout and save its configuration."""
        for name in ("candidates", "best", "logs", "exports"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.save_config(config)

    def save_config(self, config: ProjectConfig) -> None:
        """Save the current editable settings."""
        data = config.to_dict()
        data["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
        data["format_version"] = 1
        atomic_json(self.root / "opturbo_project.json", data)

    @staticmethod
    def load(path: Path) -> ProjectConfig:
        """Load a project file or a folder containing it."""
        source = Path(path)
        if source.is_dir():
            source = source / "opturbo_project.json"
        config = ProjectConfig.from_dict(json.loads(source.read_text(encoding="utf-8")))
        config.save_dir = str(source.parent)
        return config

    def candidate_dir(self, generation: int, index: int) -> Path:
        """Create and return a unique candidate folder."""
        base = self.root / "candidates" / f"generation_{generation:03d}" / f"candidate_{index:03d}"
        if not base.exists():
            base.mkdir(parents=True)
            return base
        suffix = 2
        while (alternative := base.with_name(f"{base.name}_run{suffix:02d}")).exists():
            suffix += 1
        alternative.mkdir(parents=True)
        return alternative

    def save_history(self, rows: list[dict[str, Any]]) -> None:
        """Save optimizer history for restart, plotting, and audit."""
        atomic_json(self.root / "optimization_history.json", {"evaluations": rows})

