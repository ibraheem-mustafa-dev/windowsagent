# UIA Element Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt6 transparent overlay window that draws colour-coded bounding boxes over UIA elements, with click-to-inspect, search, and "Add to profile" for community profile authoring.

**Architecture:** A standalone PyQt6 window (always-on-top, transparent background, frameless) that consumes UIA tree data from the existing `observer/uia.py` module. The overlay fetches element data via the existing HTTP API (`GET /windows`, `POST /observe`) so it runs as a separate process from the agent server. Two modules: `renderer.py` handles the transparent window and QPainter drawing; `inspector.py` handles the property panel, search, and profile export. A thin CLI command (`windowsagent overlay`) launches both.

**Tech Stack:** PyQt6 (>=6.5), existing WindowsAgent HTTP API on localhost:7862

**Key design decisions:**
- `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint` + `Qt.WidgetAttribute.WA_TranslucentBackground` for the transparent overlay
- NOT click-through -- the overlay captures clicks to inspect elements. Toggle visibility with a global hotkey (F12)
- DPI-aware: reads `get_dpi_scale()` from existing `screenshot.py`, scales all QPainter coordinates
- Colour coding by 5 functional groups (not per control type): Interactive (blue #648FFF), Text Input (amber #FFB000), Container (purple #785EF0), Navigation (magenta #DC267F), Other (grey #9AA0A6). IBM CVD-safe palette. Borders only, no fills. 3 shipped presets: Default (CVD-safe), High Contrast, Monochrome. Brand orange #FC7908 for active element highlight
- Element data fetched via `httpx.get("http://localhost:7862/observe")` -- no direct UIA calls in the overlay process
- Search uses simple substring match on element name/automation_id/control_type

---

## File Structure

```
windowsagent/
  overlay/
    __init__.py           -- Package exports (OverlayWindow, InspectorPanel, launch_overlay)
    renderer.py           -- PyQt6 transparent window, QPainter bounding box drawing, hotkey toggle
    inspector.py          -- Element property popup, search bar, "Add to profile" export
tests/
  test_overlay.py         -- Unit tests for rendering logic, search, colour mapping, profile export
```

---

## Task 1: Overlay Renderer -- Core Window and Drawing

**Files:**
- Create: `windowsagent/overlay/__init__.py`
- Create: `windowsagent/overlay/renderer.py`
- Create: `tests/test_overlay.py`

### Step 1: Write failing tests for colour mapping and element flattening

- [ ] **Step 1a: Create test file with colour mapping and flatten tests**

```python
# tests/test_overlay.py
"""Tests for UIA element overlay."""
from __future__ import annotations


class TestColourMapping:
    def test_button_is_blue(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        r, g, b, _a = colour_for_control_type("Button")
        assert (r, g, b) == (66, 133, 244)  # Google Blue

    def test_edit_is_green(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        r, g, b, _a = colour_for_control_type("Edit")
        assert (r, g, b) == (52, 168, 83)  # Green

    def test_list_is_orange(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        r, g, b, _a = colour_for_control_type("List")
        assert (r, g, b) == (251, 188, 4)  # Orange

    def test_unknown_is_grey(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        r, g, b, _a = colour_for_control_type("SomeCustomControl")
        assert (r, g, b) == (154, 160, 166)  # Grey

    def test_alpha_is_semi_transparent(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        _r, _g, _b, a = colour_for_control_type("Button")
        assert a == 60  # Semi-transparent fill


class TestFlattenTree:
    def test_flattens_nested_elements(self) -> None:
        from windowsagent.overlay.renderer import flatten_elements

        tree = {
            "name": "root", "control_type": "Window",
            "rect": [0, 0, 100, 100], "is_visible": True,
            "children": [
                {
                    "name": "btn", "control_type": "Button",
                    "rect": [10, 10, 50, 30], "is_visible": True,
                    "children": [],
                },
                {
                    "name": "hidden", "control_type": "Text",
                    "rect": [0, 0, 0, 0], "is_visible": False,
                    "children": [],
                },
            ],
        }
        visible = flatten_elements(tree)
        # Should include root + btn, exclude hidden (not visible)
        assert len(visible) == 2
        names = [e["name"] for e in visible]
        assert "btn" in names
        assert "hidden" not in names

    def test_skips_zero_rect_elements(self) -> None:
        from windowsagent.overlay.renderer import flatten_elements

        tree = {
            "name": "root", "control_type": "Window",
            "rect": [0, 0, 1920, 1080], "is_visible": True,
            "children": [
                {
                    "name": "zero", "control_type": "Pane",
                    "rect": [0, 0, 0, 0], "is_visible": True,
                    "children": [],
                },
            ],
        }
        visible = flatten_elements(tree)
        # root is visible, zero-rect element is skipped
        assert len(visible) == 1
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: FAIL (import errors -- module doesn't exist)

### Step 2: Implement colour mapping and element flattening

- [ ] **Step 2a: Create overlay package**

```python
# windowsagent/overlay/__init__.py
"""UIA element overlay -- visual debugging tool for WindowsAgent."""
from __future__ import annotations
```

- [ ] **Step 2b: Implement renderer.py with pure functions first**

```python
# windowsagent/overlay/renderer.py
"""
PyQt6 transparent overlay window for UIA element visualisation.

Draws colour-coded bounding boxes over UI Automation elements.
Fetches element data from the WindowsAgent HTTP API on localhost:7862.
Toggle visibility with F12. Click any element to inspect its properties.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Colour palette: (R, G, B, Alpha) -- alpha for semi-transparent fill
_COLOUR_MAP: dict[str, tuple[int, int, int, int]] = {
    "Button": (66, 133, 244, 60),       # Blue
    "SplitButton": (66, 133, 244, 60),
    "Edit": (52, 168, 83, 60),          # Green
    "Document": (52, 168, 83, 60),
    "ComboBox": (52, 168, 83, 60),
    "List": (251, 188, 4, 60),          # Orange
    "ListItem": (251, 188, 4, 60),
    "DataGrid": (251, 188, 4, 60),
    "Tree": (251, 188, 4, 60),
    "TreeItem": (251, 188, 4, 60),
    "MenuItem": (234, 67, 53, 60),       # Red
    "Menu": (234, 67, 53, 60),
    "MenuBar": (234, 67, 53, 60),
    "Tab": (103, 58, 183, 60),           # Purple
    "TabItem": (103, 58, 183, 60),
    "CheckBox": (0, 172, 193, 60),       # Teal
    "RadioButton": (0, 172, 193, 60),
    "Hyperlink": (25, 118, 210, 60),     # Link blue
}

_DEFAULT_COLOUR = (154, 160, 166, 60)    # Grey


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
    # A zero-area rect means the element has no screen presence
    has_area = (rect[2] - rect[0]) > 0 and (rect[3] - rect[1]) > 0

    if is_visible and has_area:
        result.append(tree)

    for child in tree.get("children", []):
        flatten_elements(child, result)

    return result
```

- [ ] **Step 2c: Run tests to verify they pass**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 2d: Run mypy**

Run: `python -m mypy windowsagent/overlay/`
Expected: 0 errors

- [ ] **Step 2e: Commit**

```bash
git add windowsagent/overlay/ tests/test_overlay.py
git commit -m "feat(overlay): colour mapping and element flattening for UIA overlay"
```

---

### Step 3: Write failing tests for the data fetcher

- [ ] **Step 3a: Add data fetcher tests**

Append to `tests/test_overlay.py`:

```python
from unittest.mock import patch, MagicMock
import json


class TestDataFetcher:
    def test_fetch_windows_returns_list(self) -> None:
        from windowsagent.overlay.renderer import fetch_windows

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "Notepad", "hwnd": 123, "rect": [0, 0, 800, 600]},
        ]
        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_resp
            windows = fetch_windows()
        assert len(windows) == 1
        assert windows[0]["title"] == "Notepad"

    def test_fetch_uia_tree_returns_tree(self) -> None:
        from windowsagent.overlay.renderer import fetch_uia_tree

        tree_data = {
            "uia_tree": {
                "root": {"name": "Notepad", "control_type": "Window",
                         "rect": [0, 0, 800, 600], "is_visible": True,
                         "children": []},
            },
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = tree_data
        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = fetch_uia_tree("Notepad")
        assert result["name"] == "Notepad"

    def test_fetch_uia_tree_returns_none_on_error(self) -> None:
        from windowsagent.overlay.renderer import fetch_uia_tree

        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.post.side_effect = Exception("Connection refused")
            result = fetch_uia_tree("Notepad")
        assert result is None
```

- [ ] **Step 3b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestDataFetcher -v`
Expected: FAIL

### Step 4: Implement data fetcher functions

- [ ] **Step 4a: Add fetch functions to renderer.py**

Add to `windowsagent/overlay/renderer.py` (after the existing code):

```python
import httpx

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
        return data.get("uia_tree", {}).get("root")  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning("Failed to fetch UIA tree for '%s': %s", window_title, exc)
        return None
```

- [ ] **Step 4b: Run tests**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 4c: Run mypy + full suite**

Run: `python -m mypy windowsagent/overlay/ && python -m pytest tests/ -m "not integration" -q`
Expected: 0 mypy errors, 267+ tests pass

- [ ] **Step 4d: Commit**

```bash
git add windowsagent/overlay/renderer.py tests/test_overlay.py
git commit -m "feat(overlay): HTTP data fetcher for UIA tree and window list"
```

---

## Task 2: Overlay Renderer -- PyQt6 Window

**Files:**
- Modify: `windowsagent/overlay/renderer.py`
- Modify: `tests/test_overlay.py`

> **Note:** The PyQt6 window class itself cannot be unit-tested without a QApplication (requires a display). Tests for this task mock the Qt layer and test the coordinate/drawing logic. Integration testing is manual (launch overlay, visually verify).

### Step 5: Write tests for DPI coordinate scaling

- [ ] **Step 5a: Add DPI scaling tests**

Append to `tests/test_overlay.py`:

```python
class TestDPIScaling:
    def test_scale_rect_at_100_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect
        # At 100% DPI (scale=1.0), rect is unchanged
        result = scale_rect((100, 200, 300, 400), dpi_scale=1.0)
        assert result == (100, 200, 300, 400)

    def test_scale_rect_at_150_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect
        # At 150% DPI (scale=1.5), logical coords are divided by scale
        # because Qt renders in physical pixels but UIA gives logical
        result = scale_rect((150, 300, 450, 600), dpi_scale=1.5)
        assert result == (100, 200, 300, 400)

    def test_scale_rect_at_200_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect
        result = scale_rect((200, 400, 600, 800), dpi_scale=2.0)
        assert result == (100, 200, 300, 400)
```

- [ ] **Step 5b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestDPIScaling -v`
Expected: FAIL

### Step 6: Implement DPI scaling and OverlayWindow class

- [ ] **Step 6a: Add scale_rect function**

Add to `windowsagent/overlay/renderer.py`:

```python
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
```

- [ ] **Step 6b: Add OverlayWindow class skeleton**

Add to `windowsagent/overlay/renderer.py`:

```python
try:
    from PyQt6.QtCore import Qt, QTimer, QRect
    from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
    from PyQt6.QtWidgets import QWidget, QApplication

    _HAS_PYQT6 = True
except ImportError:
    _HAS_PYQT6 = False


class OverlayWindow:
    """Transparent always-on-top window that draws UIA element bounding boxes.

    Requires PyQt6. Import guarded -- raises ImportError with install hint
    if PyQt6 is not available.

    Usage:
        window = OverlayWindow(target_window="Notepad")
        window.start()  # Starts the Qt event loop
    """

    def __init__(self, target_window: str, refresh_ms: int = 2000) -> None:
        if not _HAS_PYQT6:
            msg = "PyQt6 is required for the overlay. Install: pip install PyQt6"
            raise ImportError(msg)

        self.target_window = target_window
        self.refresh_ms = refresh_ms
        self.elements: list[dict[str, Any]] = []
        self.selected_element: dict[str, Any] | None = None
        self.search_query: str = ""
        self.dpi_scale: float = 1.0
        self._on_element_selected: Any = None

    def start(self) -> None:
        """Launch the overlay window. Blocks until closed."""
        app = QApplication([])
        self._widget = _OverlayWidget(self)
        self._widget.show()
        app.exec()


class _OverlayWidget(QWidget):  # type: ignore[misc]
    """Internal Qt widget for the overlay rendering."""

    def __init__(self, overlay: OverlayWindow) -> None:
        super().__init__()
        self.overlay = overlay

        # Frameless, always-on-top, transparent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # Exclude from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Full screen overlay
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)

        # Refresh timer -- polls UIA tree periodically
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_elements)
        self._timer.start(overlay.refresh_ms)

        # Initial load
        self._refresh_elements()

    def _refresh_elements(self) -> None:
        """Fetch UIA tree and flatten into drawable elements."""
        tree = fetch_uia_tree(self.overlay.target_window)
        if tree is not None:
            self.overlay.elements = flatten_elements(tree)
        self.update()  # Trigger repaint

    def paintEvent(self, event: Any) -> None:
        """Draw bounding boxes over all visible UIA elements."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        dpi = self.overlay.dpi_scale
        query = self.overlay.search_query.lower()

        for elem in self.overlay.elements:
            raw_rect = elem.get("rect", [0, 0, 0, 0])
            left, top, right, bottom = scale_rect(tuple(raw_rect), dpi)
            w = right - left
            h = bottom - top
            if w <= 0 or h <= 0:
                continue

            ct = elem.get("control_type", "")
            r, g, b, a = colour_for_control_type(ct)

            # Highlight search matches
            if query:
                name = elem.get("name", "").lower()
                aid = elem.get("automation_id", "").lower()
                if query not in name and query not in aid and query not in ct.lower():
                    a = 15  # Dim non-matching elements
                else:
                    a = 100  # Brighten matches

            # Highlight selected element
            is_selected = (
                self.overlay.selected_element is not None
                and elem.get("name") == self.overlay.selected_element.get("name")
                and elem.get("rect") == self.overlay.selected_element.get("rect")
            )
            if is_selected:
                a = 120
                painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow border
            else:
                painter.setPen(QPen(QColor(r, g, b, min(a + 80, 255)), 1))

            painter.setBrush(QBrush(QColor(r, g, b, a)))
            painter.drawRect(QRect(left, top, w, h))

            # Draw label for selected or search-matched elements
            if is_selected or (query and a > 15):
                label = f"{elem.get('name', '')} [{ct}]"
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = QFont("Segoe UI", 8)
                painter.setFont(font)
                painter.drawText(left + 2, top - 4, label)

        painter.end()

    def mousePressEvent(self, event: Any) -> None:
        """Handle click -- find which element was clicked and select it."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position()
        click_x, click_y = int(pos.x()), int(pos.y())
        dpi = self.overlay.dpi_scale

        # Find the smallest (most specific) element containing the click
        best: dict[str, Any] | None = None
        best_area = float("inf")

        for elem in self.overlay.elements:
            raw_rect = elem.get("rect", [0, 0, 0, 0])
            left, top, right, bottom = scale_rect(tuple(raw_rect), dpi)
            if left <= click_x <= right and top <= click_y <= bottom:
                area = (right - left) * (bottom - top)
                if area < best_area:
                    best = elem
                    best_area = area

        self.overlay.selected_element = best
        if best and self.overlay._on_element_selected:
            self.overlay._on_element_selected(best)
        self.update()

    def keyPressEvent(self, event: Any) -> None:
        """Handle keyboard -- Escape to close, F5 to refresh."""
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_F5:
            self._refresh_elements()
```

- [ ] **Step 6c: Run tests**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS (all 12 tests -- Qt class only instantiated if PyQt6 available)

- [ ] **Step 6d: Run mypy**

Run: `python -m mypy windowsagent/overlay/`
Expected: 0 errors

- [ ] **Step 6e: Commit**

```bash
git add windowsagent/overlay/renderer.py tests/test_overlay.py
git commit -m "feat(overlay): PyQt6 transparent window with DPI-aware bounding box rendering"
```

---

## Task 3: Inspector Panel -- Search, Properties, Profile Export

**Files:**
- Create: `windowsagent/overlay/inspector.py`
- Modify: `tests/test_overlay.py`

### Step 7: Write failing tests for search and profile export

- [ ] **Step 7a: Add search and export tests**

Append to `tests/test_overlay.py`:

```python
class TestSearchElements:
    def test_search_by_name(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "Save", "control_type": "Button", "automation_id": "btn_save"},
            {"name": "Cancel", "control_type": "Button", "automation_id": "btn_cancel"},
            {"name": "File Name", "control_type": "Edit", "automation_id": "txt_filename"},
        ]
        results = search_elements(elements, "save")
        assert len(results) == 1
        assert results[0]["name"] == "Save"

    def test_search_by_automation_id(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "OK", "control_type": "Button", "automation_id": "dlg_ok"},
            {"name": "Cancel", "control_type": "Button", "automation_id": "dlg_cancel"},
        ]
        results = search_elements(elements, "dlg_ok")
        assert len(results) == 1

    def test_search_by_control_type(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "Save", "control_type": "Button", "automation_id": ""},
            {"name": "Name", "control_type": "Edit", "automation_id": ""},
        ]
        results = search_elements(elements, "edit")
        assert len(results) == 1
        assert results[0]["name"] == "Name"

    def test_empty_query_returns_all(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "A", "control_type": "Button", "automation_id": ""},
            {"name": "B", "control_type": "Edit", "automation_id": ""},
        ]
        results = search_elements(elements, "")
        assert len(results) == 2


class TestProfileExport:
    def test_generates_known_element_entry(self) -> None:
        from windowsagent.overlay.inspector import element_to_profile_entry

        elem = {
            "name": "Save",
            "control_type": "Button",
            "automation_id": "btn_save",
            "patterns": ["invoke"],
            "rect": [100, 200, 200, 230],
        }
        entry = element_to_profile_entry(elem)
        assert entry["name"] == "Save"
        assert entry["control_type"] == "Button"
        assert entry["automation_id"] == "btn_save"
        assert "invoke" in entry["patterns"]

    def test_generates_profile_template(self) -> None:
        from windowsagent.overlay.inspector import generate_profile_snippet

        entries = [
            {"name": "Save", "control_type": "Button", "automation_id": "btn_save", "patterns": ["invoke"]},
            {"name": "Name", "control_type": "Edit", "automation_id": "txt_name", "patterns": ["value"]},
        ]
        snippet = generate_profile_snippet("myapp.exe", entries)
        assert "class MyappProfile" in snippet
        assert '"Save"' in snippet
        assert "btn_save" in snippet
        assert "BaseAppProfile" in snippet
```

- [ ] **Step 7b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestSearchElements tests/test_overlay.py::TestProfileExport -v`
Expected: FAIL

### Step 8: Implement inspector.py

- [ ] **Step 8a: Create inspector module**

```python
# windowsagent/overlay/inspector.py
"""
Element inspector -- search, property display, and profile export.

Provides search filtering over flattened UIA elements and generates
community profile code snippets from selected elements.
"""
from __future__ import annotations

import re
from typing import Any


def search_elements(
    elements: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Filter elements by substring match on name, automation_id, or control_type.

    Args:
        elements: Flat list of UIA element dicts.
        query: Search string (case-insensitive). Empty returns all.

    Returns:
        Filtered list of matching elements.
    """
    if not query:
        return elements

    q = query.lower()
    return [
        e for e in elements
        if q in e.get("name", "").lower()
        or q in e.get("automation_id", "").lower()
        or q in e.get("control_type", "").lower()
    ]


def element_to_profile_entry(element: dict[str, Any]) -> dict[str, Any]:
    """Convert a UIA element dict to a profile known_element entry.

    Returns a dict suitable for inclusion in an app profile's
    known_elements list.
    """
    return {
        "name": element.get("name", ""),
        "control_type": element.get("control_type", ""),
        "automation_id": element.get("automation_id", ""),
        "patterns": element.get("patterns", []),
    }


def generate_profile_snippet(
    app_name: str,
    entries: list[dict[str, Any]],
) -> str:
    """Generate a Python community profile class from selected elements.

    Args:
        app_name: Process name (e.g. "myapp.exe").
        entries: List of profile entries from element_to_profile_entry().

    Returns:
        Python source code string for a BaseAppProfile subclass.
    """
    # Clean class name: myapp.exe -> MyappProfile
    clean = re.sub(r"[^a-zA-Z0-9]", "", app_name.split(".")[0])
    class_name = clean.capitalize() + "Profile"

    lines = [
        f'"""Auto-generated profile for {app_name}."""',
        "from __future__ import annotations",
        "",
        "from typing import ClassVar",
        "",
        "from windowsagent.apps.base import BaseAppProfile",
        "",
        "",
        f"class {class_name}(BaseAppProfile):",
        f'    """Profile for {app_name}."""',
        "",
        f'    app_names: ClassVar[list[str]] = ["{app_name}"]',
        "    window_titles: ClassVar[list[str]] = []",
        "",
        "    known_elements: ClassVar[list[dict[str, str]]] = [",
    ]

    for entry in entries:
        name = entry.get("name", "")
        ct = entry.get("control_type", "")
        aid = entry.get("automation_id", "")
        lines.append(f'        {{"name": "{name}", "control_type": "{ct}", "automation_id": "{aid}"}},')

    lines.append("    ]")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 8b: Run tests**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS (all 18 tests)

- [ ] **Step 8c: Run mypy + full suite**

Run: `python -m mypy windowsagent/overlay/ && python -m pytest tests/ -m "not integration" -q`
Expected: 0 mypy errors, 267+ tests pass

- [ ] **Step 8d: Commit**

```bash
git add windowsagent/overlay/inspector.py tests/test_overlay.py
git commit -m "feat(overlay): element search, property inspector, and profile code generation"
```

---

## Task 4: CLI Command and Package Wiring

**Files:**
- Modify: `windowsagent/overlay/__init__.py`
- Modify: `windowsagent/cli.py`
- Modify: `tests/test_overlay.py`
- Modify: `pyproject.toml`

### Step 9: Write failing test for CLI command

- [ ] **Step 9a: Add CLI test**

Append to `tests/test_overlay.py`:

```python
from click.testing import CliRunner


class TestOverlayCLI:
    def test_overlay_command_exists(self) -> None:
        from windowsagent.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["overlay", "--help"])
        assert result.exit_code == 0
        assert "overlay" in result.output.lower()

    def test_overlay_requires_window(self) -> None:
        from windowsagent.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["overlay"])
        # Should fail without --window
        assert result.exit_code != 0
```

- [ ] **Step 9b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestOverlayCLI -v`
Expected: FAIL

### Step 10: Implement CLI command and wire up exports

- [ ] **Step 10a: Update __init__.py exports**

```python
# windowsagent/overlay/__init__.py
"""UIA element overlay -- visual debugging tool for WindowsAgent."""
from __future__ import annotations

from windowsagent.overlay.renderer import (
    OverlayWindow,
    colour_for_control_type,
    flatten_elements,
    fetch_uia_tree,
    fetch_windows,
    scale_rect,
)
from windowsagent.overlay.inspector import (
    search_elements,
    element_to_profile_entry,
    generate_profile_snippet,
)

__all__ = [
    "OverlayWindow",
    "colour_for_control_type",
    "flatten_elements",
    "fetch_uia_tree",
    "fetch_windows",
    "scale_rect",
    "search_elements",
    "element_to_profile_entry",
    "generate_profile_snippet",
]
```

- [ ] **Step 10b: Add CLI command**

Add to `windowsagent/cli.py`:

```python
@cli.command(name="overlay")
@click.option("--window", required=True, help="Target window title")
@click.option("--refresh", default=2000, help="Refresh interval in ms (default: 2000)")
def overlay_cmd(window: str, refresh: int) -> None:
    """Launch the UIA element overlay for visual debugging.

    Draws colour-coded bounding boxes over UI elements in the target window.
    Click any element to inspect its properties. Press Escape to close.
    """
    from windowsagent.overlay.renderer import OverlayWindow

    overlay = OverlayWindow(target_window=window, refresh_ms=refresh)
    click.echo(f"Launching overlay for '{window}' (refresh every {refresh}ms)")
    click.echo("Press Escape to close. Click elements to inspect.")
    overlay.start()
```

- [ ] **Step 10c: Add PyQt6 to optional dependencies in pyproject.toml**

Add `overlay` optional group:

```toml
[project.optional-dependencies]
overlay = ["PyQt6>=6.5"]
```

- [ ] **Step 10d: Run tests**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS (all 20 tests)

- [ ] **Step 10e: Run full suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/overlay/ windowsagent/cli.py`
Expected: 267+ tests pass, 0 mypy errors

- [ ] **Step 10f: Commit**

```bash
git add windowsagent/overlay/__init__.py windowsagent/cli.py pyproject.toml tests/test_overlay.py
git commit -m "feat(overlay): CLI command and PyQt6 optional dependency"
```

---

## Task 5: Integration Wiring and Polish

**Files:**
- Modify: `windowsagent/overlay/renderer.py`
- Modify: `windowsagent/overlay/__init__.py`
- Modify: `ARCHITECTURE.md`

### Step 11: Add DPI auto-detection to OverlayWindow

- [ ] **Step 11a: Wire DPI detection from screenshot module**

In `OverlayWindow.__init__`, after `self.dpi_scale = 1.0`, add:

```python
try:
    from windowsagent.observer.screenshot import get_dpi_scale
    self.dpi_scale = get_dpi_scale()
except Exception:
    self.dpi_scale = 1.0  # Safe fallback
```

- [ ] **Step 11b: Run full test suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 267+ tests pass

### Step 12: Update ARCHITECTURE.md

- [ ] **Step 12a: Add overlay section to ARCHITECTURE.md**

Add a new section 3.23 documenting the overlay module: purpose, public API, dependencies, integration points.

- [ ] **Step 12b: Commit**

```bash
git add windowsagent/overlay/ ARCHITECTURE.md
git commit -m "feat(overlay): DPI auto-detection and architecture documentation"
```

### Step 13: Final verification

- [ ] **Step 13a: Run full test suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 267+ tests pass (new overlay tests included)

- [ ] **Step 13b: Run mypy on entire codebase**

Run: `python -m mypy windowsagent/`
Expected: 0 errors

- [ ] **Step 13c: Run ruff**

Run: `python -m ruff check windowsagent/overlay/`
Expected: 0 errors (ignore pre-existing RUF005 in routes/system.py)

---

## Guardrails

- **Tests:** 267+ unit tests must keep passing after every commit. Run `python -m pytest tests/ -m "not integration" -q`
- **Types:** mypy must stay at 0 errors. Run `python -m mypy windowsagent/`
- **Lint:** ruff 0 new warnings. 2 pre-existing RUF005 in routes/system.py -- ignore.
- **File limits:** Python files under 250 lines. `renderer.py` is the largest -- monitor its size.
- **PyQt6 import guard:** All PyQt6 imports behind `try/except ImportError`. Module works without PyQt6 installed (pure functions still importable for testing).
- **No direct UIA calls:** Overlay fetches data via HTTP API only. This keeps it process-isolated.
