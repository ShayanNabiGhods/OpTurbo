"""Scrollable settings panels used in dense application tabs."""

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """A settings container that shows a vertical scrollbar only when needed."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self._scrollbar_visible = False
        self.body = ttk.Frame(self.canvas, padding=8)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body.bind("<Configure>", self._content_changed)
        self.canvas.bind("<Configure>", self._canvas_resized)

    def _content_changed(self, _event: object = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._schedule_scrollbar_check()

    def _canvas_resized(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window, width=event.width)
        self._schedule_scrollbar_check()

    def _schedule_scrollbar_check(self) -> None:
        if not getattr(self, "_scroll_check_pending", False):
            self._scroll_check_pending = True
            self.after_idle(self._update_scrollbar_visibility)

    def _update_scrollbar_visibility(self) -> None:
        self._scroll_check_pending = False
        if not self.winfo_exists():
            return
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        viewport_height = self.canvas.winfo_height()
        content_height = self.body.winfo_reqheight()
        should_show = viewport_height > 1 and content_height > viewport_height + 2
        if should_show == self._scrollbar_visible:
            return
        self._scrollbar_visible = should_show
        if should_show:
            self.scrollbar.pack(side="right", fill="y")
        else:
            self.scrollbar.pack_forget()
            self.canvas.yview_moveto(0)
