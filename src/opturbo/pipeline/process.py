"""Cross-platform subprocess helpers with live log streaming."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Callable


def windows_path(path: Path) -> str:
    """Return a Windows path when running under WSL, otherwise a native path."""
    resolved = str(Path(path).resolve())
    if os.name != "nt" and resolved.startswith("/mnt/"):
        drive, remainder = resolved[5], resolved[7:]
        return f"{drive.upper()}:\\{remainder.replace('/', chr(92))}"
    return resolved


def executable_path(configured: str) -> str:
    """Translate a configured Windows drive path for execution from WSL."""
    if os.name != "nt" and len(configured) > 2 and configured[1:3] == ":\\":
        return f"/mnt/{configured[0].lower()}/{configured[3:].replace(chr(92), '/')}"
    return configured


def run_streaming(command: list[str], cwd: Path, log_path: Path, emit: Callable[[str], None]) -> None:
    """Run a command, append combined output to a log, and raise on failure."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    emit("$ " + " ".join(command))
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip()
            log.write(line)
            emit(clean)
        status = process.wait()
    if status:
        raise RuntimeError(f"Command failed with exit code {status}: {command[0]}")
