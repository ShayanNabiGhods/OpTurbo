"""Hover help for Tkinter controls."""

import tkinter as tk


class ToolTip:
    """Show a short explanation when the pointer rests over a GUI control."""

    def __init__(self, widget: tk.Misc, text: str):
        self.widget, self.text, self.window = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event: object = None) -> None:
        if self.window or not self.text:
            return
        x, y = self.widget.winfo_rootx() + 16, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        tk.Label(self.window, text=self.text, justify="left", wraplength=360,
                 background="#20242a", foreground="#f5f7fa", padx=8, pady=5).pack()

    def _hide(self, _event: object = None) -> None:
        if self.window:
            self.window.destroy()
            self.window = None
