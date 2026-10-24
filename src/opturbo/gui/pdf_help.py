"""Open the manual at a field-specific named section from a help button."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
import webbrowser
from tkinter import messagebox, ttk

from ..paths import APPLICATION_ROOT
from .widgets import ToolTip


DOCS_ROOT = APPLICATION_ROOT / "docs"


def _edge_pdf_executable() -> Path | None:
    """Find Edge only when Windows has registered it as the PDF viewer."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        if str(prog_id).lower() != "msedgepdf":
            return None
    except (OSError, ImportError):
        return None

    candidates = []
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Microsoft Edge" / "Application" / "msedge.exe")
    return next((path for path in candidates if path.is_file()), None)


def _open_pdf_destination(path: Path, destination: str) -> bool:
    """Open the existing PDF file at its named section destination."""
    edge = _edge_pdf_executable()
    url = f"{path.resolve().as_uri()}#nameddest={quote(destination, safe='')}"
    if edge is not None:
        try:
            subprocess.Popen([str(edge), url], close_fds=True)
            return True
        except OSError:
            pass
    return bool(webbrowser.open_new_tab(url))


def open_manual_topic(topic: str, label: str = "") -> None:
    """Open the bundled manual at the named section for one GUI option."""
    manual = DOCS_ROOT / "manual.pdf"
    index_path = DOCS_ROOT / "manual_help_index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        section = index.get("field_topics", {}).get(topic, "start-here")
        destinations = set(index.get("manual_destinations", []))
        destination = section if section in destinations else "start-here"
        if destination not in destinations:
            raise ValueError("The manual index does not contain its start section.")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        messagebox.showerror("Manual unavailable", "The OpTurbo manual page index could not be read.")
        return
    if not manual.is_file():
        messagebox.showerror("Manual unavailable", f"The user manual is missing:\n{manual}")
        return
    try:
        if not _open_pdf_destination(manual, destination):
            messagebox.showerror("Cannot open manual", "No browser is available to display the PDF manual.")
    except (OSError, webbrowser.Error) as error:
        messagebox.showerror("Cannot open manual", f"Could not open the manual for {label or topic}:\n{error}")


def open_guide(filename: str) -> None:
    """Open one of the bundled PDF guides in the system's default viewer."""
    path = DOCS_ROOT / filename
    if not path.is_file():
        messagebox.showerror("Guide unavailable", f"The OpTurbo guide is missing:\n{path}")
        return
    try:
        if not webbrowser.open_new_tab(path.resolve().as_uri()):
            messagebox.showerror("Cannot open guide", "No browser is available to display the PDF guide.")
    except (OSError, webbrowser.Error) as error:
        messagebox.showerror("Cannot open guide", f"Could not open {filename}:\n{error}")


def add_pdf_help_button(
    parent: ttk.Frame, row: int, topic: str, label: str = "", column: int = 2,
) -> ttk.Button:
    """Place a compact, keyboard-accessible manual button beside an option."""
    button = ttk.Button(
        parent,
        text="?",
        width=2,
        command=lambda: open_manual_topic(topic, label),
        takefocus=True,
    )
    button.grid(row=row, column=column, sticky="w", padx=(1, 3), pady=2)
    ToolTip(button, f"Open the user manual section for {label or topic}.")
    return button
