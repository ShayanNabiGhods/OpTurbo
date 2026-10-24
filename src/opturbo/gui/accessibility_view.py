"""Focused Tkinter behavior for the OpTurbo application."""

import tkinter as tk
from tkinter import ttk

from .widgets import ScrollableFrame, ToolTip
from .pdf_help import add_pdf_help_button


class AccessibilityViewMixin:
    def _build_accessibility_tab(self) -> None:
        """Build visual and keyboard-use settings that are safe to change at runtime."""
        tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(tab, text="  Accessibility  ")
        settings_scroll = ScrollableFrame(tab)
        settings_scroll.pack(fill="both", expand=True)
        panel = ttk.LabelFrame(settings_scroll.body, text="Display and interaction", padding=14)
        panel.pack(anchor="nw", fill="x")
        ttk.Label(panel, text="Appearance", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Choose a colour theme, enlarge text, or enable high contrast. Changes apply immediately and are saved with the project.",
                  style="Subtitle.TLabel", wraplength=680, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        self.theme_var = tk.StringVar(value="light")
        self.text_scale_var = tk.StringVar(value="100")
        self.high_contrast_var = tk.BooleanVar(value=False)
        self.accent_var = tk.StringVar(value="#2f6fed")
        self.candidate_marker_size_var = tk.StringVar(value="5")
        self.outer_marker_size_var = tk.StringVar(value="5")
        self.table_row_spacing_var = tk.StringVar(value="0")
        ttk.Label(panel, text="Theme").grid(row=2, column=0, sticky="w", pady=5)
        theme = ttk.Combobox(panel, textvariable=self.theme_var, values=("light", "dark"), state="readonly", width=14)
        theme.grid(row=2, column=1, sticky="w", pady=5)
        add_pdf_help_button(panel, 2, "accessibility", "Theme")
        ttk.Label(panel, text="Light uses the default palette; dark reduces screen brightness.", style="Subtitle.TLabel", wraplength=420).grid(row=3, column=1, sticky="w")
        ttk.Label(panel, text="Text size").grid(row=4, column=0, sticky="w", pady=(12, 5))
        text_scale = ttk.Combobox(panel, textvariable=self.text_scale_var, values=("90", "100", "110", "125", "150", "175", "200"), state="readonly", width=14)
        text_scale.grid(row=4, column=1, sticky="w", pady=(12, 5))
        add_pdf_help_button(panel, 4, "accessibility", "Text size")
        ttk.Label(panel, text="Scales interface text from 90% to 150%.", style="Subtitle.TLabel").grid(row=5, column=1, sticky="w")
        contrast = ttk.Checkbutton(panel, text="High contrast", variable=self.high_contrast_var, command=self._apply_accessibility)
        contrast.grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 2))
        add_pdf_help_button(panel, 6, "accessibility", "High contrast")
        ttk.Label(panel, text="Uses a black background, white text, and a bright focus colour for maximum contrast.",
                  style="Subtitle.TLabel", wraplength=520).grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Keyboard use", style="Title.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(22, 0))
        ttk.Label(panel, text="Use Tab and Shift+Tab to move between controls, Space to toggle checkboxes, and Enter to activate a focused button. Hover any control for a short explanation.",
                  style="Subtitle.TLabel", wraplength=680, justify="left").grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        theme.bind("<<ComboboxSelected>>", self._apply_accessibility)
        text_scale.bind("<<ComboboxSelected>>", self._apply_accessibility)
        ToolTip(theme, "Switch between light and dark appearance.")
        ToolTip(text_scale, "Change the size of text throughout the application.")
        ToolTip(contrast, "Increase colour contrast for easier reading.")
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Accent color (blue / teal / purple / orange)").grid(row=10, column=0, sticky="w", pady=12)
        accent = ttk.Combobox(panel, textvariable=self.accent_var, values=("#2f6fed", "#007d79", "#7540a8", "#a74700"), state="readonly", width=14)
        accent.grid(row=10, column=1, sticky="w")
        add_pdf_help_button(panel, 10, "accessibility", "Accent color")
        accent.bind("<<ComboboxSelected>>", self._apply_accessibility)
        ttk.Label(panel, text="Accent highlights selected tabs, primary actions and progress. High contrast overrides it.", style="Subtitle.TLabel").grid(row=11, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="Candidate marker size").grid(row=12, column=0, sticky="w", pady=(12, 5))
        candidate_markers = ttk.Combobox(panel, textvariable=self.candidate_marker_size_var,
                                         values=tuple(str(size) for size in range(2, 13)), state="readonly", width=14)
        candidate_markers.grid(row=12, column=1, sticky="w", pady=(12, 5))
        add_pdf_help_button(panel, 12, "accessibility", "Candidate marker size")
        ttk.Label(panel, text="Marker size for candidate results in the Candidates panel.", style="Subtitle.TLabel").grid(row=13, column=1, sticky="w")
        ttk.Label(panel, text="Outer Cp / Ct marker size").grid(row=14, column=0, sticky="w", pady=(8, 5))
        outer_markers = ttk.Combobox(panel, textvariable=self.outer_marker_size_var,
                                     values=tuple(str(size) for size in range(2, 13)), state="readonly", width=14)
        outer_markers.grid(row=14, column=1, sticky="w", pady=(8, 5))
        add_pdf_help_button(panel, 14, "accessibility", "Outer Cp / Ct marker size")
        ttk.Label(panel, text="Marker size for the Outer Cp / Ct panel.", style="Subtitle.TLabel").grid(row=15, column=1, sticky="w")
        candidate_markers.bind("<<ComboboxSelected>>", self._apply_accessibility)
        outer_markers.bind("<<ComboboxSelected>>", self._apply_accessibility)
        ttk.Label(panel, text="Table row spacing").grid(row=16, column=0, sticky="w", pady=(12, 5))
        row_spacing = ttk.Combobox(panel, textvariable=self.table_row_spacing_var,
                                   values=tuple(str(value) for value in range(0, 21, 2)),
                                   state="readonly", width=14)
        row_spacing.grid(row=16, column=1, sticky="w", pady=(12, 5))
        add_pdf_help_button(panel, 16, "accessibility", "Table row spacing")
        ttk.Label(panel, text="Extra vertical space between rows in all tables, in pixels.",
                  style="Subtitle.TLabel").grid(row=17, column=1, sticky="w")
        row_spacing.bind("<<ComboboxSelected>>", self._apply_accessibility)
