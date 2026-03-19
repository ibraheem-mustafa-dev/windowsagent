"""
Colour schemes and functional group mapping for UIA overlay.

Defines the ColourScheme dataclass, 3 preset factories, and the mapping
from UIA control types to 5 functional groups. Pure functions -- no
PyQt6 dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Pen style constants (mirror Qt.PenStyle values for pure-function testing)
# ---------------------------------------------------------------------------
PEN_STYLE_SOLID = 1      # Qt.PenStyle.SolidLine
PEN_STYLE_DASH = 2       # Qt.PenStyle.DashLine
PEN_STYLE_DOT = 3        # Qt.PenStyle.DotLine
PEN_STYLE_DASH_DOT = 4   # Qt.PenStyle.DashDotLine

# Border widths
ACTIVE_BORDER_WIDTH = 4
SELECTED_BORDER_WIDTH = 3
DEFAULT_BORDER_WIDTH = 2


@dataclass(frozen=True)
class ColourScheme:
    """Colour scheme for overlay bounding boxes.

    Each field is an (R, G, B, A) tuple. The 5 functional groups cover
    all UIA control types. Special states override group colours.
    """

    interactive: tuple[int, int, int, int]
    text_input: tuple[int, int, int, int]
    container: tuple[int, int, int, int]
    navigation: tuple[int, int, int, int]
    other: tuple[int, int, int, int]
    selected: tuple[int, int, int, int]
    dimmed: tuple[int, int, int, int]
    active: tuple[int, int, int, int]


def default_scheme() -> ColourScheme:
    """IBM CVD-safe palette -- default preset."""
    return ColourScheme(
        interactive=(100, 143, 255, 200),    # #648FFF blue
        text_input=(255, 176, 0, 200),       # #FFB000 amber
        container=(120, 94, 240, 200),       # #785EF0 purple
        navigation=(220, 38, 127, 200),      # #DC267F magenta
        other=(154, 160, 166, 200),          # #9AA0A6 grey
        selected=(17, 135, 149, 255),        # #118795 brand teal
        dimmed=(154, 160, 166, 40),
        active=(252, 121, 8, 255),           # #FC7908 brand orange
    )


def high_contrast_scheme() -> ColourScheme:
    """High contrast preset for maximum visibility."""
    return ColourScheme(
        interactive=(255, 255, 255, 255),
        text_input=(255, 255, 0, 255),
        container=(0, 255, 255, 255),
        navigation=(255, 0, 255, 255),
        other=(192, 192, 192, 255),
        selected=(0, 255, 0, 255),
        dimmed=(80, 80, 80, 100),
        active=(255, 165, 0, 255),
    )


def monochrome_scheme() -> ColourScheme:
    """Single-colour preset -- differentiation by pen style only."""
    mono = (200, 200, 200, 180)
    return ColourScheme(
        interactive=mono,
        text_input=mono,
        container=mono,
        navigation=mono,
        other=mono,
        selected=(255, 255, 255, 255),
        dimmed=(100, 100, 100, 60),
        active=(252, 121, 8, 255),
    )


# ---------------------------------------------------------------------------
# Control type to functional group mapping
# ---------------------------------------------------------------------------
CONTROL_TYPE_GROUPS: dict[str, str] = {
    "Button": "interactive",
    "SplitButton": "interactive",
    "CheckBox": "interactive",
    "RadioButton": "interactive",
    "ComboBox": "interactive",
    "Slider": "interactive",
    "Spinner": "interactive",
    "ScrollBar": "interactive",
    "Thumb": "interactive",
    "Edit": "text_input",
    "Document": "text_input",
    "List": "container",
    "ListItem": "container",
    "DataGrid": "container",
    "DataItem": "container",
    "Tree": "container",
    "TreeItem": "container",
    "Table": "container",
    "Group": "container",
    "Menu": "navigation",
    "MenuBar": "navigation",
    "MenuItem": "navigation",
    "Tab": "navigation",
    "TabItem": "navigation",
    "Hyperlink": "navigation",
    "ToolBar": "navigation",
}

_GROUP_PEN_STYLES: dict[str, int] = {
    "interactive": PEN_STYLE_SOLID,
    "text_input": PEN_STYLE_DASH,
    "container": PEN_STYLE_DOT,
    "navigation": PEN_STYLE_DASH_DOT,
    "other": PEN_STYLE_SOLID,
}


def group_for_control_type(control_type: str) -> str:
    """Return the functional group name for a UIA control type."""
    return CONTROL_TYPE_GROUPS.get(control_type, "other")


def colour_for_element(
    control_type: str,
    scheme: ColourScheme,
) -> tuple[tuple[int, int, int, int], str, int]:
    """Return (colour, group_name, pen_style) for a control type and scheme."""
    group = group_for_control_type(control_type)
    colour: tuple[int, int, int, int] = getattr(scheme, group)
    pen_style = _GROUP_PEN_STYLES.get(group, PEN_STYLE_SOLID)
    return colour, group, pen_style


def colour_for_control_type(control_type: str) -> tuple[int, int, int, int]:
    """Backward-compatible: return (R, G, B, A) for a control type."""
    colour, _group, _pen = colour_for_element(control_type, default_scheme())
    return colour
