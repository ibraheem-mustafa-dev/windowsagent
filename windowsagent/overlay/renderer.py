"""
PyQt6 transparent overlay window for UIA element visualisation.

Draws colour-coded bounding boxes over UI Automation elements.
Fetches element data from the WindowsAgent HTTP API on localhost:7862.
Toggle visibility with F12. Click any element to inspect its properties.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Colour palette: (R, G, B, Alpha) -- alpha for semi-transparent fill
_COLOUR_MAP: dict[str, tuple[int, int, int, int]] = {
    "Button": (66, 133, 244, 60),
    "SplitButton": (66, 133, 244, 60),
    "Edit": (52, 168, 83, 60),
    "Document": (52, 168, 83, 60),
    "ComboBox": (52, 168, 83, 60),
    "List": (251, 188, 4, 60),
    "ListItem": (251, 188, 4, 60),
    "DataGrid": (251, 188, 4, 60),
    "Tree": (251, 188, 4, 60),
    "TreeItem": (251, 188, 4, 60),
    "MenuItem": (234, 67, 53, 60),
    "Menu": (234, 67, 53, 60),
    "MenuBar": (234, 67, 53, 60),
    "Tab": (103, 58, 183, 60),
    "TabItem": (103, 58, 183, 60),
    "CheckBox": (0, 172, 193, 60),
    "RadioButton": (0, 172, 193, 60),
    "Hyperlink": (25, 118, 210, 60),
}

_DEFAULT_COLOUR = (154, 160, 166, 60)


def colour_for_control_type(control_type: str) -> tuple[int, int, int, int]:
    """Return (R, G, B, A) colour tuple for a UIA control type."""
    return _COLOUR_MAP.get(control_type, _DEFAULT_COLOUR)


def flatten_elements(
    tree: dict[str, Any],
    result: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Flatten a nested UIA tree dict into a list of visible elements.

    Skips elements that are not visible or have zero-area bounding rects.

    Args:
        tree: UIA tree dict from the /observe API response.
        result: Accumulator (internal use).

    Returns:
        Flat list of element dicts with non-zero visible rects.
    """
    if result is None:
        result = []

    rect = tree.get("rect", [0, 0, 0, 0])
    is_visible = tree.get("is_visible", False)
    has_area = (rect[2] - rect[0]) > 0 and (rect[3] - rect[1]) > 0

    if is_visible and has_area:
        result.append(tree)

    for child in tree.get("children", []):
        flatten_elements(child, result)

    return result


def scale_rect(
    rect: tuple[int, int, int, int],
    dpi_scale: float,
) -> tuple[int, int, int, int]:
    """Scale a UIA logical-pixel rect for Qt rendering.

    UIA returns coordinates in logical pixels. When DPI scaling is active
    (e.g. 150%), Qt's coordinate system already accounts for scaling,
    so we divide by the scale factor to get the correct screen position.

    Args:
        rect: (left, top, right, bottom) in UIA logical pixels.
        dpi_scale: DPI scale factor (e.g. 1.0, 1.5, 2.0).

    Returns:
        Scaled (left, top, right, bottom) tuple.
    """
    if dpi_scale <= 0:
        dpi_scale = 1.0
    left, top, right, bottom = rect
    return (
        round(left / dpi_scale),
        round(top / dpi_scale),
        round(right / dpi_scale),
        round(bottom / dpi_scale),
    )


BASE_URL = "http://localhost:7862"


def fetch_windows() -> list[dict[str, Any]]:
    """Fetch list of visible windows from WindowsAgent API."""
    try:
        resp = httpx.get(f"{BASE_URL}/windows", timeout=5.0)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning("Failed to fetch windows: %s", exc)
        return []


def fetch_uia_tree(window_title: str) -> dict[str, Any] | None:
    """Fetch UIA tree for a window from WindowsAgent API.

    Returns the root element dict, or None on failure.
    """
    try:
        resp = httpx.post(
            f"{BASE_URL}/observe",
            json={"window": window_title},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        tree = data.get("uia_tree", {})
        # API returns the root element directly under uia_tree (no "root" wrapper)
        if "children" in tree:
            return tree  # type: ignore[no-any-return]
        # Fallback: some responses may nest under "root"
        return tree.get("root")  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning("Failed to fetch UIA tree for '%s': %s", window_title, exc)
        return None


# ---------------------------------------------------------------------------
# PyQt6 overlay window (optional dependency)
# ---------------------------------------------------------------------------

try:
    from PyQt6.QtWidgets import QApplication

    _HAS_PYQT6 = True
except ImportError:
    _HAS_PYQT6 = False


class OverlayWindow:
    """Transparent always-on-top window that draws UIA element bounding boxes.

    Requires PyQt6. Import guarded -- raises ImportError if not available.
    """

    def __init__(self, target_window: str, refresh_ms: int = 2000) -> None:
        if not _HAS_PYQT6:
            msg = "PyQt6 required for overlay. Install: pip install PyQt6"
            raise ImportError(msg)

        self.target_window = target_window
        self.refresh_ms = refresh_ms
        self.elements: list[dict[str, Any]] = []
        self.selected_element: dict[str, Any] | None = None
        self.search_query: str = ""
        self.dpi_scale: float = 1.0
        self._on_element_selected: Any = None

        try:
            from windowsagent.observer.screenshot import get_dpi_scale
            self.dpi_scale = get_dpi_scale()
        except Exception:
            self.dpi_scale = 1.0

    def start(self) -> None:
        """Launch the overlay window. Blocks until closed."""
        from windowsagent.overlay.widget import OverlayWidget

        app = QApplication([])
        widget = OverlayWidget(self)
        widget.show()
        # QApplication event loop (not shell execution)
        app.exec()
