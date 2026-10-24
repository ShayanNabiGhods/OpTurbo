"""Cross-platform subprocess helpers with live log streaming."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
import shutil
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


def require_executable(configured: str, display_name: str) -> str:
    """Return the execution path or fail before launching an external tool."""
    resolved = executable_path(configured)
    candidate = Path(resolved).expanduser()
    if candidate.is_file():
        return str(candidate)
    if not Path(resolved).is_absolute() and shutil.which(resolved):
        return resolved
    raise FileNotFoundError(
        f"{display_name} executable was not found at the configured path: {configured}"
    )


def run_streaming(command: list[str], cwd: Path, log_path: Path, emit: Callable[[str], None], cancel: Callable[[], bool] | None = None) -> None:
    """Run a command, append combined output to a log, and raise on failure."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if cancel and cancel():
        raise RuntimeError("Process terminated by user")
    emit("$ " + " ".join(command))
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert process.stdout is not None
        finished = threading.Event()

        def watch_cancel() -> None:
            """Stop only this launched process tree, even when stdout is quiet."""
            while not finished.wait(0.1):
                if cancel and cancel() and process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, check=False)
                    else:
                        process.kill()
                    return

        watcher = threading.Thread(target=watch_cancel, daemon=True)
        watcher.start()
        try:
            for line in process.stdout:
                log.write(line)
                log.flush()
                emit(line.rstrip())
            status = process.wait()
        finally:
            finished.set()
            watcher.join()
            process.stdout.close()
    if cancel and cancel():
        raise RuntimeError("Process terminated by user")
    if status:
        raise RuntimeError(f"Command failed with exit code {status}: {command[0]}")
