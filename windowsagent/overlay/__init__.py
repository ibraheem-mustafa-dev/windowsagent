"""UIA element overlay -- visual debugging tool for WindowsAgent."""
from __future__ import annotations

from windowsagent.overlay.inspector import (
    element_to_profile_entry,
    generate_profile_snippet,
    search_elements,
)
from windowsagent.overlay.renderer import (
    OverlayWindow,
    colour_for_control_type,
    fetch_uia_tree,
    fetch_windows,
    flatten_elements,
    scale_rect,
)

__all__ = [
    "OverlayWindow",
    "colour_for_control_type",
    "element_to_profile_entry",
    "fetch_uia_tree",
    "fetch_windows",
    "flatten_elements",
    "generate_profile_snippet",
    "scale_rect",
    "search_elements",
]
