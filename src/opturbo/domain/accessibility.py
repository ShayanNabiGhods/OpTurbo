"""Saved user-interface accessibility preferences."""

from dataclasses import dataclass


@dataclass
class AccessibilitySettings:
    """Store visual preferences that make the desktop interface easier to use."""

    theme: str = "light"
    text_scale: int = 100
    high_contrast: bool = False
    accent_color: str = "#2f6fed"
    candidate_marker_size: int = 5
    outer_marker_size: int = 5
    table_row_spacing: int = 0
