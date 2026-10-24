"""Open the manual at a field-specific named section from a help button."""

from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import quote
import webbrowser
from tkinter import messagebox, ttk

from ..paths import APPLICATION_ROOT
from .widgets import ToolTip


DOCS_ROOT = APPLICATION_ROOT / "docs"
_DOCS_SERVER: ThreadingHTTPServer | None = None
_DOCS_SERVER_LOCK = Lock()


class _QuietDocsHandler(SimpleHTTPRequestHandler):
    """Serve bundled guides locally without writing request logs to the console."""

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep routine browser requests out of the application's console."""


def _docs_http_server() -> ThreadingHTTPServer:
    """Start one loopback-only server so PDF viewers honor section fragments.

    Several PDF viewers ignore named-destination fragments on ``file://``
    URLs. Serving only the bundled docs directory over loopback HTTP lets the
    PDF viewer process the standard ``nameddest`` fragment correctly.
    """
    global _DOCS_SERVER
    with _DOCS_SERVER_LOCK:
        if _DOCS_SERVER is None:
            handler = partial(_QuietDocsHandler, directory=str(DOCS_ROOT))
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            Thread(target=server.serve_forever, name="opturbo-docs", daemon=True).start()
            _DOCS_SERVER = server
        return _DOCS_SERVER


def _docs_url(filename: str, destination: str | None = None) -> str:
    """Build a localhost URL to a bundled guide, optionally targeting a section."""
    server = _docs_http_server()
    url = f"http://127.0.0.1:{server.server_port}/{quote(filename, safe='/')}"
    if destination:
        url += f"#nameddest={quote(destination, safe='')}"
    return url


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
    """Open a PDF at a named section through a loopback HTTP URL."""
    edge = _edge_pdf_executable()
    url = _docs_url(path.name, destination)
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
        if not webbrowser.open_new_tab(_docs_url(path.name)):
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
