"""Open the bundled PDF guides from the application interface."""

from pathlib import Path
import webbrowser
from tkinter import messagebox

from ..paths import APPLICATION_ROOT


DOCS_ROOT = APPLICATION_ROOT / "docs"


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
