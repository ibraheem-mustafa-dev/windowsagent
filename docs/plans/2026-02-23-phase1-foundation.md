# WindowsAgent Phase 1: Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reliable observe-act-verify foundation for Windows desktop automation, without LLM/vision integration.

**Architecture:** UIA-first desktop automation with pywinauto as the primary interface. Each action follows observe (UIA tree + screenshot) -> act (UIA patterns, pyautogui fallback) -> verify (screenshot diff + UIA state check). App-specific profiles handle quirks like WebView2 virtualised lists.

**Tech Stack:** Python 3.13, pywinauto (UIA backend), pyautogui, mss, Pillow, Flask. pytest for testing.

**Existing code:** Working prototype at `C:\Users\Bean\.openclaw\workspace\tools\desktop-agent\server.py` — reference it for patterns but do not copy wholesale. The prototype has issues (no WebView2 handling, no verification, no app profiles, single 480-line file).

---

## Task 1: Git Init + Package Scaffold

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/windowsagent/__init__.py`
- Create: `src/windowsagent/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Initialise git repo**

Run: `git init`

**Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.eggs/
venv/
.venv/
*.png
*.jpg
*.bmp
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

**Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "windowsagent"
version = "0.1.0"
description = "Open-source AI agent that controls Windows desktop apps reliably"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
dependencies = [
    "pywinauto>=0.6.8",
    "pyautogui>=0.9.54",
    "mss>=9.0",
    "Pillow>=10.0",
    "flask>=3.0",
]

[project.optional-dependencies]
vision = ["google-generativeai>=0.4", "anthropic>=0.18"]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[project.scripts]
windowsagent = "windowsagent.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/windowsagent"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: requires a real Windows desktop app to be open",
]
```

**Step 4: Create directory structure**

```
src/windowsagent/__init__.py
src/windowsagent/config.py
src/windowsagent/observer/__init__.py
src/windowsagent/actor/__init__.py
src/windowsagent/verifier/__init__.py
src/windowsagent/apps/__init__.py
tests/__init__.py
tests/conftest.py
```

**Step 5: Write `src/windowsagent/config.py`**

```python
"""WindowsAgent configuration."""

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Core configuration for WindowsAgent."""

    # Observer
    uia_tree_max_depth: int = 4
    screenshot_format: str = "png"

    # Actor
    pyautogui_pause: float = 0.1
    pyautogui_failsafe: bool = True
    click_retry_count: int = 1
    type_interval: float = 0.02

    # Verifier
    verify_after_action: bool = True
    verify_screenshot_delay: float = 0.3
    screenshot_diff_threshold: float = 0.01

    # Scroll
    scroll_page_pause: float = 0.5
    scroll_max_attempts: int = 20

    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 7862
```

**Step 6: Write `src/windowsagent/__init__.py`**

```python
"""WindowsAgent - AI desktop automation for Windows."""

__version__ = "0.1.0"
```

**Step 7: Write `tests/conftest.py`**

```python
"""Shared test fixtures for WindowsAgent."""

import pytest
from windowsagent.config import AgentConfig


@pytest.fixture
def config():
    """Default test configuration."""
    return AgentConfig()
```

**Step 8: Install package in dev mode and run empty test suite**

Run: `cd /c/Users/Bean/Projects/windowsagent && pip install -e ".[dev]"`
Run: `pytest tests/ -v`
Expected: 0 tests collected, no errors.

**Step 9: Commit**

```bash
git add .gitignore pyproject.toml src/ tests/ docs/ README.md CLAUDE-CODE-BRIEF.md
git commit -m "chore: scaffold package structure with config and test setup"
```

---

## Task 2: Observer - UIA Tree Inspection

**Files:**
- Create: `src/windowsagent/observer/uia.py`
- Create: `tests/test_observer_uia.py`

**Step 1: Write `src/windowsagent/observer/uia.py`**

This module wraps pywinauto's UIA backend. Key functions:
- `connect_to_window(title=None, pid=None)` -> returns pywinauto window wrapper
- `list_windows()` -> returns list of visible window info dicts
- `get_control_tree(window, max_depth)` -> nested dict of controls
- `get_interactive_elements(window)` -> flat list of clickable/typeable controls with index

Reference the prototype's `_find_window`, `_control_to_dict`, and `inspect_flat` for the approach, but improve:
- Add `automation_id` and `class_name` to all outputs
- Add control patterns (is_invocable, is_selectable, has_value) to element info
- Filter `get_interactive_elements` to visible+enabled controls only
- Handle `ElementNotFoundError` and `TimeoutError` gracefully

```python
"""UI Automation tree inspection via pywinauto."""

from __future__ import annotations

from typing import Optional

from pywinauto import Application, Desktop
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.config import AgentConfig


def list_windows() -> list[dict]:
    """List all visible windows with title, pid, and bounding rect."""
    windows = []
    desktop = Desktop(backend="uia")
    for win in desktop.windows():
        try:
            if not win.is_visible():
                continue
            title = win.element_info.name
            if not title:
                continue
            rect = win.rectangle()
            windows.append({
                "title": title,
                "pid": win.element_info.process_id,
                "class_name": win.element_info.class_name or "",
                "rect": _rect_to_dict(rect),
            })
        except Exception:
            continue
    return windows


def connect_to_window(
    title: Optional[str] = None,
    pid: Optional[int] = None,
    timeout: int = 5,
) -> UIAWrapper:
    """Connect to a window by title regex or process ID.

    Returns the top-level window wrapper.
    Raises ConnectionError if no matching window found.
    """
    try:
        if pid:
            app = Application(backend="uia").connect(process=pid, timeout=timeout)
        elif title:
            app = Application(backend="uia").connect(
                title_re=f".*{title}.*", timeout=timeout, found_index=0,
            )
        else:
            raise ValueError("Provide either title or pid")
        return app.top_window()
    except Exception as exc:
        raise ConnectionError(f"Could not connect to window: {exc}") from exc


def get_control_tree(
    window: UIAWrapper,
    max_depth: int = 4,
) -> dict:
    """Walk the UIA tree and return a nested dict of controls."""
    return _control_to_dict(window, depth=0, max_depth=max_depth)


def get_interactive_elements(window: UIAWrapper) -> list[dict]:
    """Return a flat, indexed list of visible interactive controls.

    Each element includes: index, control_type, name, automation_id,
    class_name, rect, enabled, patterns.
    """
    interactive_types = {
        "Button", "Edit", "ComboBox", "CheckBox", "RadioButton",
        "Slider", "Tab", "TabItem", "MenuItem", "Menu",
        "Hyperlink", "ListItem", "TreeItem", "DataItem",
        "Document", "ScrollBar",
    }
    elements: list[dict] = []
    _walk_interactive(window, interactive_types, elements)
    return elements


# -- Private helpers --

def _rect_to_dict(rect) -> dict:
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": rect.width(),
        "height": rect.height(),
        "mid_x": rect.mid_point().x,
        "mid_y": rect.mid_point().y,
    }


def _get_patterns(ctrl: UIAWrapper) -> list[str]:
    """Return list of supported UIA pattern names for a control."""
    patterns = []
    try:
        iface = ctrl.iface_invoke
        if iface:
            patterns.append("Invoke")
    except Exception:
        pass
    try:
        iface = ctrl.iface_value
        if iface:
            patterns.append("Value")
    except Exception:
        pass
    try:
        iface = ctrl.iface_selection_item
        if iface:
            patterns.append("SelectionItem")
    except Exception:
        pass
    try:
        iface = ctrl.iface_scroll
        if iface:
            patterns.append("Scroll")
    except Exception:
        pass
    try:
        iface = ctrl.iface_toggle
        if iface:
            patterns.append("Toggle")
    except Exception:
        pass
    return patterns


def _control_to_dict(ctrl: UIAWrapper, depth: int = 0, max_depth: int = 4) -> dict:
    """Serialise a control to a dict, recursing into children."""
    try:
        info = {
            "control_type": ctrl.element_info.control_type or "Unknown",
            "name": ctrl.element_info.name or "",
            "class_name": ctrl.element_info.class_name or "",
            "automation_id": getattr(ctrl.element_info, "automation_id", "") or "",
            "rect": _rect_to_dict(ctrl.rectangle()),
            "is_enabled": ctrl.is_enabled(),
            "is_visible": ctrl.is_visible(),
        }
    except Exception:
        return {"error": "Could not read control properties"}

    if depth < max_depth:
        children = []
        try:
            for child in ctrl.children():
                children.append(_control_to_dict(child, depth + 1, max_depth))
        except Exception:
            pass
        if children:
            info["children"] = children

    return info


def _walk_interactive(
    ctrl: UIAWrapper,
    interactive_types: set[str],
    elements: list[dict],
) -> None:
    """Recursively walk tree, appending interactive elements to list."""
    try:
        ct = ctrl.element_info.control_type or ""
        visible = ctrl.is_visible()
        enabled = ctrl.is_enabled()

        if ct in interactive_types and visible and enabled:
            rect = ctrl.rectangle()
            elements.append({
                "index": len(elements),
                "control_type": ct,
                "name": ctrl.element_info.name or "",
                "automation_id": getattr(ctrl.element_info, "automation_id", "") or "",
                "class_name": ctrl.element_info.class_name or "",
                "rect": _rect_to_dict(rect),
                "enabled": enabled,
                "patterns": _get_patterns(ctrl),
            })
    except Exception:
        pass

    try:
        for child in ctrl.children():
            _walk_interactive(child, interactive_types, elements)
    except Exception:
        pass
```

**Step 2: Write `tests/test_observer_uia.py`**

```python
"""Tests for UIA observer module."""

import pytest
from windowsagent.observer.uia import (
    list_windows,
    connect_to_window,
    get_control_tree,
    get_interactive_elements,
)


class TestListWindows:
    """Tests for list_windows (always works, no app required)."""

    def test_returns_list(self):
        result = list_windows()
        assert isinstance(result, list)

    def test_each_window_has_required_keys(self):
        result = list_windows()
        assert len(result) > 0, "No visible windows found"
        for win in result:
            assert "title" in win
            assert "pid" in win
            assert "rect" in win

    def test_no_empty_titles(self):
        result = list_windows()
        for win in result:
            assert win["title"], "Window title should not be empty"


class TestConnectToWindow:
    """Tests for connecting to a window."""

    def test_raises_on_no_args(self):
        with pytest.raises(ValueError, match="title or pid"):
            connect_to_window()

    def test_raises_connection_error_for_nonexistent_window(self):
        with pytest.raises(ConnectionError):
            connect_to_window(title="ThisWindowDefinitelyDoesNotExist12345")


@pytest.mark.integration
class TestNotepadInspection:
    """Integration tests requiring Notepad to be open.

    Run: open Notepad first, then pytest -m integration
    """

    def test_connect_to_notepad(self):
        win = connect_to_window(title="Notepad")
        assert win is not None

    def test_get_control_tree(self):
        win = connect_to_window(title="Notepad")
        tree = get_control_tree(win, max_depth=3)
        assert tree["control_type"] == "Window"
        assert "children" in tree

    def test_get_interactive_elements(self):
        win = connect_to_window(title="Notepad")
        elements = get_interactive_elements(win)
        assert isinstance(elements, list)
        assert len(elements) > 0, "Notepad should have interactive elements"
        # Notepad has at least an Edit control
        types = {el["control_type"] for el in elements}
        assert "Edit" in types or "Document" in types
```

**Step 3: Run non-integration tests**

Run: `pytest tests/test_observer_uia.py -v -m "not integration"`
Expected: 4 tests pass.

**Step 4: Commit**

```bash
git add src/windowsagent/observer/ tests/test_observer_uia.py
git commit -m "feat: add UIA tree observer with window listing and control inspection"
```

---

## Task 3: Observer - Screenshot Capture

**Files:**
- Create: `src/windowsagent/observer/screenshot.py`
- Create: `tests/test_observer_screenshot.py`

**Step 1: Write `src/windowsagent/observer/screenshot.py`**

Use `mss` for fast capture (not pyautogui — mss is 3-10x faster). Key functions:
- `capture_screen()` -> PIL Image of entire screen
- `capture_window(window)` -> PIL Image of specific window (from UIA rect)
- `capture_region(left, top, width, height)` -> PIL Image of region
- `image_to_base64(image)` -> base64-encoded PNG string
- `images_differ(img_a, img_b, threshold)` -> bool (for verification)

```python
"""Screenshot capture using mss for speed."""

from __future__ import annotations

import base64
import io

import mss
from PIL import Image
from pywinauto.controls.uiawrapper import UIAWrapper


def capture_screen(monitor: int = 0) -> Image.Image:
    """Capture the entire screen (or a specific monitor).

    monitor=0 captures all monitors combined.
    monitor=1 is the primary monitor.
    """
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[monitor])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def capture_window(window: UIAWrapper) -> Image.Image:
    """Capture a screenshot of a specific window by its UIA rect."""
    rect = window.rectangle()
    return capture_region(rect.left, rect.top, rect.width(), rect.height())


def capture_region(left: int, top: int, width: int, height: int) -> Image.Image:
    """Capture a specific screen region."""
    monitor = {"left": left, "top": top, "width": width, "height": height}
    with mss.mss() as sct:
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    """Encode a PIL Image as a base64 string."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def images_differ(
    img_a: Image.Image,
    img_b: Image.Image,
    threshold: float = 0.01,
) -> bool:
    """Compare two images. Returns True if they differ beyond threshold.

    Threshold is fraction of pixels that differ (0.0 = identical, 1.0 = completely different).
    Resizes to match if dimensions differ.
    """
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size)

    pixels_a = list(img_a.getdata())
    pixels_b = list(img_b.getdata())
    total = len(pixels_a)

    if total == 0:
        return False

    diff_count = sum(1 for a, b in zip(pixels_a, pixels_b) if a != b)
    return (diff_count / total) > threshold
```

**Step 2: Write `tests/test_observer_screenshot.py`**

```python
"""Tests for screenshot capture module."""

import pytest
from PIL import Image
from windowsagent.observer.screenshot import (
    capture_screen,
    capture_region,
    image_to_base64,
    images_differ,
)


class TestCaptureScreen:
    def test_returns_pil_image(self):
        img = capture_screen()
        assert isinstance(img, Image.Image)

    def test_image_has_pixels(self):
        img = capture_screen()
        assert img.width > 0
        assert img.height > 0


class TestCaptureRegion:
    def test_captures_small_region(self):
        img = capture_region(0, 0, 100, 100)
        assert img.size == (100, 100)


class TestImageToBase64:
    def test_returns_string(self):
        img = Image.new("RGB", (10, 10), colour=(255, 0, 0))
        result = image_to_base64(img)
        assert isinstance(result, str)
        assert len(result) > 0


class TestImagesDiffer:
    def test_identical_images_do_not_differ(self):
        img = Image.new("RGB", (10, 10), colour=(255, 0, 0))
        assert images_differ(img, img) is False

    def test_different_images_differ(self):
        img_a = Image.new("RGB", (10, 10), colour=(255, 0, 0))
        img_b = Image.new("RGB", (10, 10), colour=(0, 0, 255))
        assert images_differ(img_a, img_b) is True

    def test_threshold_controls_sensitivity(self):
        img_a = Image.new("RGB", (100, 100), colour=(255, 0, 0))
        img_b = img_a.copy()
        # Change 5% of pixels
        for x in range(10):
            for y in range(50):
                img_b.putpixel((x, y), (0, 255, 0))
        assert images_differ(img_a, img_b, threshold=0.01) is True
        assert images_differ(img_a, img_b, threshold=0.10) is False
```

**Step 3: Run tests**

Run: `pytest tests/test_observer_screenshot.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/windowsagent/observer/screenshot.py tests/test_observer_screenshot.py
git commit -m "feat: add screenshot capture with mss and image comparison"
```

---

## Task 4: Observer - Combined State

**Files:**
- Create: `src/windowsagent/observer/state.py`
- Modify: `src/windowsagent/observer/__init__.py`
- Create: `tests/test_observer_state.py`

**Step 1: Write `src/windowsagent/observer/state.py`**

A `WindowState` dataclass that bundles UIA tree + screenshot + interactive elements into a single snapshot.

```python
"""Combined window state representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PIL import Image
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.observer.uia import (
    connect_to_window,
    get_control_tree,
    get_interactive_elements,
)
from windowsagent.observer.screenshot import capture_window, image_to_base64
from windowsagent.config import AgentConfig


@dataclass
class WindowState:
    """Snapshot of a window's current state."""

    window_title: str
    control_tree: dict
    interactive_elements: list[dict]
    screenshot: Optional[Image.Image] = field(default=None, repr=False)
    screenshot_b64: Optional[str] = field(default=None, repr=False)

    def find_element(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Find first interactive element matching criteria."""
        for el in self.interactive_elements:
            if name and name.lower() not in el["name"].lower():
                continue
            if control_type and el["control_type"] != control_type:
                continue
            if automation_id and el["automation_id"] != automation_id:
                continue
            return el
        return None

    def find_elements(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> list[dict]:
        """Find all interactive elements matching criteria."""
        results = []
        for el in self.interactive_elements:
            if name and name.lower() not in el["name"].lower():
                continue
            if control_type and el["control_type"] != control_type:
                continue
            results.append(el)
        return results


def observe_window(
    title: Optional[str] = None,
    pid: Optional[int] = None,
    config: Optional[AgentConfig] = None,
    include_screenshot: bool = True,
) -> WindowState:
    """Capture complete state of a window.

    Returns a WindowState with UIA tree, interactive elements,
    and optionally a screenshot.
    """
    if config is None:
        config = AgentConfig()

    window = connect_to_window(title=title, pid=pid)
    tree = get_control_tree(window, max_depth=config.uia_tree_max_depth)
    elements = get_interactive_elements(window)

    screenshot = None
    screenshot_b64 = None
    if include_screenshot:
        screenshot = capture_window(window)
        screenshot_b64 = image_to_base64(screenshot, fmt=config.screenshot_format.upper())

    return WindowState(
        window_title=window.element_info.name or "",
        control_tree=tree,
        interactive_elements=elements,
        screenshot=screenshot,
        screenshot_b64=screenshot_b64,
    )
```

**Step 2: Update `src/windowsagent/observer/__init__.py`**

```python
"""Observer module - captures window state."""

from windowsagent.observer.state import WindowState, observe_window
from windowsagent.observer.uia import list_windows, connect_to_window
from windowsagent.observer.screenshot import capture_screen, capture_window

__all__ = [
    "WindowState",
    "observe_window",
    "list_windows",
    "connect_to_window",
    "capture_screen",
    "capture_window",
]
```

**Step 3: Write `tests/test_observer_state.py`**

```python
"""Tests for combined window state."""

import pytest
from windowsagent.observer.state import WindowState


class TestWindowStateFindElement:
    def _make_state(self, elements):
        return WindowState(
            window_title="Test",
            control_tree={},
            interactive_elements=elements,
        )

    def test_find_by_name(self):
        state = self._make_state([
            {"index": 0, "name": "Save", "control_type": "Button", "automation_id": ""},
            {"index": 1, "name": "Cancel", "control_type": "Button", "automation_id": ""},
        ])
        result = state.find_element(name="Save")
        assert result is not None
        assert result["name"] == "Save"

    def test_find_by_name_case_insensitive(self):
        state = self._make_state([
            {"index": 0, "name": "Save As", "control_type": "Button", "automation_id": ""},
        ])
        result = state.find_element(name="save as")
        assert result is not None

    def test_find_by_control_type(self):
        state = self._make_state([
            {"index": 0, "name": "Search", "control_type": "Edit", "automation_id": ""},
            {"index": 1, "name": "Go", "control_type": "Button", "automation_id": ""},
        ])
        result = state.find_element(control_type="Edit")
        assert result["name"] == "Search"

    def test_find_returns_none_when_not_found(self):
        state = self._make_state([
            {"index": 0, "name": "OK", "control_type": "Button", "automation_id": ""},
        ])
        assert state.find_element(name="Nonexistent") is None

    def test_find_elements_returns_all_matches(self):
        state = self._make_state([
            {"index": 0, "name": "Item 1", "control_type": "ListItem", "automation_id": ""},
            {"index": 1, "name": "Item 2", "control_type": "ListItem", "automation_id": ""},
            {"index": 2, "name": "OK", "control_type": "Button", "automation_id": ""},
        ])
        results = state.find_elements(control_type="ListItem")
        assert len(results) == 2
```

**Step 4: Run tests**

Run: `pytest tests/test_observer_state.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/windowsagent/observer/ tests/test_observer_state.py
git commit -m "feat: add combined WindowState observer with element search"
```

---

## Task 5: Actor - UIA Actions

**Files:**
- Create: `src/windowsagent/actor/uia_actor.py`
- Create: `tests/test_actor_uia.py`

**Step 1: Write `src/windowsagent/actor/uia_actor.py`**

UIA-pattern-based actions. Each function takes a pywinauto window + element criteria, finds the control, and acts on it using UIA patterns (not coordinates).

```python
"""UIA pattern-based actions via pywinauto."""

from __future__ import annotations

from typing import Optional

from pywinauto.controls.uiawrapper import UIAWrapper


class UIAActor:
    """Execute actions via UIA automation patterns."""

    def __init__(self, window: UIAWrapper):
        self.window = window

    def click(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> dict:
        """Click a control using UIA Invoke pattern, falling back to click_input."""
        ctrl = self._find_control(name, control_type, automation_id)

        # Try Invoke pattern first (no focus issues)
        try:
            ctrl.invoke()
            return {"ok": True, "method": "invoke", "control": ctrl.element_info.name}
        except Exception:
            pass

        # Fall back to click_input (simulates real click)
        ctrl.click_input()
        return {"ok": True, "method": "click_input", "control": ctrl.element_info.name}

    def type_text(
        self,
        text: str,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        clear_first: bool = False,
    ) -> dict:
        """Type text into a control using UIA Value pattern or type_keys."""
        ctrl = self._find_control(
            name, control_type or "Edit", automation_id,
        )

        if clear_first:
            try:
                ctrl.set_text("")
            except Exception:
                ctrl.type_keys("^a{DELETE}")

        # Try Value pattern first
        try:
            iface = ctrl.iface_value
            if iface:
                ctrl.set_text(text)
                return {"ok": True, "method": "set_text", "text": text}
        except Exception:
            pass

        # Fall back to type_keys
        ctrl.type_keys(text, with_spaces=True)
        return {"ok": True, "method": "type_keys", "text": text}

    def select(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> dict:
        """Select an item using SelectionItem pattern."""
        ctrl = self._find_control(name, control_type, automation_id)
        try:
            ctrl.select()
            return {"ok": True, "method": "select", "control": ctrl.element_info.name}
        except Exception:
            ctrl.click_input()
            return {"ok": True, "method": "click_fallback", "control": ctrl.element_info.name}

    def toggle(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> dict:
        """Toggle a checkbox or toggle button."""
        ctrl = self._find_control(name, control_type, automation_id)
        ctrl.toggle()
        return {"ok": True, "method": "toggle", "control": ctrl.element_info.name}

    def get_value(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> str:
        """Read the current value of a control."""
        ctrl = self._find_control(name, control_type, automation_id)
        try:
            return ctrl.get_value()
        except Exception:
            try:
                return ctrl.window_text()
            except Exception:
                return ""

    def _find_control(
        self,
        name: Optional[str],
        control_type: Optional[str],
        automation_id: Optional[str],
    ) -> UIAWrapper:
        """Find a child control by criteria. Raises ElementNotFoundError."""
        criteria = {}
        if name:
            criteria["title"] = name
        if control_type:
            criteria["control_type"] = control_type
        if automation_id:
            criteria["auto_id"] = automation_id

        if not criteria:
            raise ValueError("Provide at least one of: name, control_type, automation_id")

        return self.window.child_window(**criteria).wrapper_object()
```

**Step 2: Write `tests/test_actor_uia.py`**

```python
"""Tests for UIA actor."""

import pytest
from windowsagent.actor.uia_actor import UIAActor


class TestUIAActorValidation:
    """Unit tests that don't need a real window."""

    def test_find_control_raises_without_criteria(self):
        """Passing no criteria should raise ValueError."""
        # We need a mock window - but since UIAActor.__init__ just stores it,
        # we can pass None and test the validation in _find_control
        actor = UIAActor(window=None)
        with pytest.raises(ValueError, match="at least one"):
            actor._find_control(None, None, None)


@pytest.mark.integration
class TestUIAActorNotepad:
    """Integration tests requiring Notepad to be open."""

    def test_type_text(self):
        from windowsagent.observer.uia import connect_to_window

        win = connect_to_window(title="Notepad")
        actor = UIAActor(win)
        result = actor.type_text("Hello WindowsAgent", clear_first=True)
        assert result["ok"] is True

    def test_get_value_from_edit(self):
        from windowsagent.observer.uia import connect_to_window

        win = connect_to_window(title="Notepad")
        actor = UIAActor(win)
        actor.type_text("test value", clear_first=True)
        value = actor.get_value(control_type="Edit")
        assert "test value" in value
```

**Step 3: Run non-integration tests**

Run: `pytest tests/test_actor_uia.py -v -m "not integration"`
Expected: 1 test passes.

**Step 4: Commit**

```bash
git add src/windowsagent/actor/uia_actor.py tests/test_actor_uia.py
git commit -m "feat: add UIA actor with click, type, select, toggle, get_value"
```

---

## Task 6: Actor - Input Fallback + Keyboard

**Files:**
- Create: `src/windowsagent/actor/input_actor.py`
- Create: `tests/test_actor_input.py`

**Step 1: Write `src/windowsagent/actor/input_actor.py`**

Coordinate-based fallback using pyautogui, plus keyboard shortcuts and clipboard.

```python
"""Coordinate-based input actions via pyautogui."""

from __future__ import annotations

import time
from typing import Optional

import pyautogui

from windowsagent.config import AgentConfig


class InputActor:
    """Execute actions via direct mouse/keyboard input (pyautogui)."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig()
        pyautogui.FAILSAFE = config.pyautogui_failsafe
        pyautogui.PAUSE = config.pyautogui_pause

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
        """Click at screen coordinates."""
        pyautogui.click(x, y, button=button, clicks=clicks)
        return {"ok": True, "method": "coordinate_click", "x": x, "y": y}

    def double_click(self, x: int, y: int) -> dict:
        """Double-click at screen coordinates."""
        pyautogui.doubleClick(x, y)
        return {"ok": True, "method": "double_click", "x": x, "y": y}

    def right_click(self, x: int, y: int) -> dict:
        """Right-click at screen coordinates."""
        pyautogui.rightClick(x, y)
        return {"ok": True, "method": "right_click", "x": x, "y": y}

    def type_text(self, text: str, interval: float = 0.02) -> dict:
        """Type text at current focus using keyboard events."""
        pyautogui.write(text, interval=interval)
        return {"ok": True, "method": "keyboard_type", "text": text}

    def press_key(self, key: str) -> dict:
        """Press a single key (enter, tab, escape, etc.)."""
        pyautogui.press(key)
        return {"ok": True, "method": "press", "key": key}

    def hotkey(self, *keys: str) -> dict:
        """Press a keyboard shortcut (e.g. hotkey('ctrl', 's'))."""
        pyautogui.hotkey(*keys)
        return {"ok": True, "method": "hotkey", "keys": list(keys)}

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> dict:
        """Scroll at position. Negative = down, positive = up."""
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        return {"ok": True, "method": "scroll", "clicks": clicks}

    def move_to(self, x: int, y: int) -> dict:
        """Move mouse to coordinates without clicking."""
        pyautogui.moveTo(x, y)
        return {"ok": True, "method": "move", "x": x, "y": y}


def clipboard_get() -> str:
    """Read text from Windows clipboard."""
    import subprocess
    result = subprocess.run(
        ["powershell", "-Command", "Get-Clipboard"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip()


def clipboard_set(text: str) -> None:
    """Write text to Windows clipboard."""
    import subprocess
    subprocess.run(
        ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
        capture_output=True, text=True, timeout=5,
    )
```

**Step 2: Write `tests/test_actor_input.py`**

```python
"""Tests for input actor (non-destructive tests only)."""

import pytest
from windowsagent.actor.input_actor import InputActor, clipboard_get, clipboard_set


class TestInputActorInit:
    def test_creates_with_defaults(self):
        actor = InputActor()
        assert actor is not None


class TestClipboard:
    def test_set_and_get(self):
        clipboard_set("windowsagent_test_123")
        result = clipboard_get()
        assert "windowsagent_test_123" in result
```

**Step 3: Run tests**

Run: `pytest tests/test_actor_input.py -v`
Expected: All pass.

**Step 4: Update `src/windowsagent/actor/__init__.py`**

```python
"""Actor module - executes actions on windows."""

from windowsagent.actor.uia_actor import UIAActor
from windowsagent.actor.input_actor import InputActor, clipboard_get, clipboard_set

__all__ = ["UIAActor", "InputActor", "clipboard_get", "clipboard_set"]
```

**Step 5: Commit**

```bash
git add src/windowsagent/actor/ tests/test_actor_input.py
git commit -m "feat: add input actor with coordinate actions, keyboard, and clipboard"
```

---

## Task 7: Scroll Strategies + WebView2 Handler

**Files:**
- Create: `src/windowsagent/webview2.py`
- Create: `tests/test_webview2.py`

**Step 1: Write `src/windowsagent/webview2.py`**

The key insight: WebView2 apps (new Outlook, Teams, VS Code) use `Chrome_WidgetWin_1` as their content class. Mouse scroll often fails to reach the inner content. Page Down/Up keys work reliably.

```python
"""WebView2 detection and special handling."""

from __future__ import annotations

import time
from typing import Optional

import pyautogui
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.observer.screenshot import capture_window, images_differ
from windowsagent.config import AgentConfig

WEBVIEW2_CLASS_NAMES = {
    "Chrome_WidgetWin_1",
    "Chrome_WidgetWin_0",
    "Chrome_RenderWidgetHostHWND",
}


def is_webview2(window: UIAWrapper) -> bool:
    """Detect if a window contains WebView2 content.

    Walks one level deep looking for Chrome_WidgetWin_* class names.
    """
    try:
        cls = window.element_info.class_name or ""
        if cls in WEBVIEW2_CLASS_NAMES:
            return True
        for child in window.children():
            child_cls = child.element_info.class_name or ""
            if child_cls in WEBVIEW2_CLASS_NAMES:
                return True
    except Exception:
        pass
    return False


def scroll_webview2(
    window: UIAWrapper,
    direction: str = "down",
    pages: int = 1,
    config: Optional[AgentConfig] = None,
) -> dict:
    """Scroll WebView2 content using keyboard (Page Down/Up).

    Mouse scroll doesn't reach WebView2 inner content reliably.
    This clicks in the content area first to ensure focus, then uses
    Page Down/Up keys.
    """
    if config is None:
        config = AgentConfig()

    key = "pagedown" if direction == "down" else "pageup"

    # Click in the centre of the window to ensure focus
    rect = window.rectangle()
    mid_x = rect.mid_point().x
    mid_y = rect.mid_point().y
    pyautogui.click(mid_x, mid_y)
    time.sleep(0.2)

    before = capture_window(window)

    for _ in range(pages):
        pyautogui.press(key)
        time.sleep(config.scroll_page_pause)

    after = capture_window(window)
    scrolled = images_differ(before, after, threshold=config.screenshot_diff_threshold)

    return {
        "ok": True,
        "method": "webview2_keyboard_scroll",
        "direction": direction,
        "pages": pages,
        "content_changed": scrolled,
    }


def find_in_virtualised_list(
    window: UIAWrapper,
    target_text: str,
    config: Optional[AgentConfig] = None,
) -> Optional[dict]:
    """Scroll through a virtualised list to find an item by text.

    WebView2 virtualised lists only expose items currently in view.
    This scrolls page by page, checking the UIA tree each time,
    until the target is found or we reach the bottom.

    Returns the element dict if found, None if not found.
    """
    if config is None:
        config = AgentConfig()

    from windowsagent.observer.uia import get_interactive_elements

    for attempt in range(config.scroll_max_attempts):
        elements = get_interactive_elements(window)
        for el in elements:
            if target_text.lower() in el.get("name", "").lower():
                return el

        # Scroll down one page
        result = scroll_webview2(window, direction="down", pages=1, config=config)

        # If content didn't change, we've hit the bottom
        if not result["content_changed"]:
            return None

    return None
```

**Step 2: Write `tests/test_webview2.py`**

```python
"""Tests for WebView2 detection and handling."""

import pytest
from unittest.mock import MagicMock
from windowsagent.webview2 import is_webview2, WEBVIEW2_CLASS_NAMES


class TestIsWebView2:
    def test_detects_chrome_widget_class(self):
        window = MagicMock()
        window.element_info.class_name = "Chrome_WidgetWin_1"
        window.children.return_value = []
        assert is_webview2(window) is True

    def test_detects_in_children(self):
        child = MagicMock()
        child.element_info.class_name = "Chrome_WidgetWin_1"

        window = MagicMock()
        window.element_info.class_name = "ApplicationFrameWindow"
        window.children.return_value = [child]
        assert is_webview2(window) is True

    def test_returns_false_for_native_window(self):
        window = MagicMock()
        window.element_info.class_name = "Notepad"
        child = MagicMock()
        child.element_info.class_name = "Edit"
        window.children.return_value = [child]
        assert is_webview2(window) is False

    def test_handles_exception_gracefully(self):
        window = MagicMock()
        window.element_info.class_name = None
        window.children.side_effect = Exception("Access denied")
        assert is_webview2(window) is False
```

**Step 3: Run tests**

Run: `pytest tests/test_webview2.py -v`
Expected: All 4 pass.

**Step 4: Commit**

```bash
git add src/windowsagent/webview2.py tests/test_webview2.py
git commit -m "feat: add WebView2 detection, keyboard scroll, and virtualised list search"
```

---

## Task 8: Verifier

**Files:**
- Create: `src/windowsagent/verifier/verify.py`
- Modify: `src/windowsagent/verifier/__init__.py`
- Create: `tests/test_verifier.py`

**Step 1: Write `src/windowsagent/verifier/verify.py`**

```python
"""Action verification — confirms an action had the expected effect."""

from __future__ import annotations

import time
from typing import Optional

from PIL import Image
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.observer.screenshot import capture_window, images_differ
from windowsagent.observer.uia import get_interactive_elements
from windowsagent.config import AgentConfig


class Verifier:
    """Verify that actions produced the expected result."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()

    def screenshot_changed(
        self,
        window: UIAWrapper,
        before: Image.Image,
    ) -> bool:
        """Check if the window looks different after an action."""
        time.sleep(self.config.verify_screenshot_delay)
        after = capture_window(window)
        return images_differ(before, after, threshold=self.config.screenshot_diff_threshold)

    def element_appeared(
        self,
        window: UIAWrapper,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> bool:
        """Check if a specific element now exists in the UIA tree."""
        elements = get_interactive_elements(window)
        for el in elements:
            if name and name.lower() not in el.get("name", "").lower():
                continue
            if control_type and el.get("control_type") != control_type:
                continue
            if automation_id and el.get("automation_id") != automation_id:
                continue
            return True
        return False

    def element_disappeared(
        self,
        window: UIAWrapper,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> bool:
        """Check if a specific element no longer exists."""
        return not self.element_appeared(window, name=name, control_type=control_type)

    def text_changed(
        self,
        window: UIAWrapper,
        control_name: Optional[str] = None,
        control_type: str = "Edit",
        expected_text: Optional[str] = None,
    ) -> bool:
        """Check if a text control contains expected text."""
        elements = get_interactive_elements(window)
        for el in elements:
            if control_name and control_name.lower() not in el.get("name", "").lower():
                continue
            if el.get("control_type") != control_type:
                continue
            # Found the control — read its value via pywinauto
            try:
                from windowsagent.observer.uia import connect_to_window
                # Re-find the specific control to read its value
                ctrl = window.child_window(
                    control_type=control_type,
                    **({"title": control_name} if control_name else {}),
                )
                value = ctrl.get_value() if hasattr(ctrl, "get_value") else ctrl.window_text()
                if expected_text:
                    return expected_text.lower() in value.lower()
                return bool(value)
            except Exception:
                return False
        return False
```

**Step 2: Update `src/windowsagent/verifier/__init__.py`**

```python
"""Verifier module - confirms actions succeeded."""

from windowsagent.verifier.verify import Verifier

__all__ = ["Verifier"]
```

**Step 3: Write `tests/test_verifier.py`**

```python
"""Tests for action verifier."""

import pytest
from PIL import Image
from windowsagent.verifier.verify import Verifier


class TestVerifierImageComparison:
    def test_detects_change(self):
        verifier = Verifier()
        before = Image.new("RGB", (100, 100), colour=(255, 0, 0))
        after = Image.new("RGB", (100, 100), colour=(0, 0, 255))
        # images_differ is tested separately; here we just confirm
        # Verifier uses it correctly via screenshot_changed.
        # Since screenshot_changed calls capture_window, we test
        # the underlying comparison function directly.
        from windowsagent.observer.screenshot import images_differ
        assert images_differ(before, after) is True

    def test_identical_means_no_change(self):
        from windowsagent.observer.screenshot import images_differ
        img = Image.new("RGB", (100, 100), colour=(128, 128, 128))
        assert images_differ(img, img) is False
```

**Step 4: Run tests**

Run: `pytest tests/test_verifier.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/windowsagent/verifier/ tests/test_verifier.py
git commit -m "feat: add action verifier with screenshot diff and element checks"
```

---

## Task 9: App Profiles

**Files:**
- Create: `src/windowsagent/apps/base.py`
- Create: `src/windowsagent/apps/notepad.py`
- Create: `src/windowsagent/apps/file_explorer.py`
- Create: `src/windowsagent/apps/outlook.py`
- Modify: `src/windowsagent/apps/__init__.py`
- Create: `tests/test_apps.py`

**Step 1: Write `src/windowsagent/apps/base.py`**

```python
"""Base app profile defining the interface all profiles implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pywinauto.controls.uiawrapper import UIAWrapper


class AppProfile(ABC):
    """Base class for app-specific automation profiles.

    Each profile knows:
    - How to identify its app (class names, title patterns)
    - How to scroll its content (native vs WebView2)
    - Shortcuts and quirks specific to the app
    """

    name: str = "generic"
    title_pattern: str = ""
    class_names: set[str] = set()

    @classmethod
    def matches(cls, window: UIAWrapper) -> bool:
        """Check if this profile matches the given window."""
        try:
            title = (window.element_info.name or "").lower()
            cls_name = window.element_info.class_name or ""
            if cls.class_names and cls_name in cls.class_names:
                return True
            if cls.title_pattern and cls.title_pattern.lower() in title:
                return True
        except Exception:
            pass
        return False

    @abstractmethod
    def scroll(self, window: UIAWrapper, direction: str = "down", amount: int = 1) -> dict:
        """Scroll content in this app."""

    def focus_panel(self, window: UIAWrapper, panel_name: str) -> dict:
        """Focus a specific panel (override for multi-panel apps)."""
        return {"ok": False, "reason": "not supported"}

    def navigate_to(self, window: UIAWrapper, target: str) -> dict:
        """Navigate to a target (file path, URL, etc). Override per app."""
        return {"ok": False, "reason": "not supported"}
```

**Step 2: Write `src/windowsagent/apps/notepad.py`**

```python
"""Notepad app profile — simplest test case."""

from __future__ import annotations

import pyautogui
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.apps.base import AppProfile


class NotepadProfile(AppProfile):
    name = "notepad"
    title_pattern = "notepad"
    class_names = {"Notepad", "ApplicationFrameWindow"}

    def scroll(self, window: UIAWrapper, direction: str = "down", amount: int = 1) -> dict:
        """Notepad: standard mouse scroll works."""
        clicks = -3 * amount if direction == "down" else 3 * amount
        rect = window.rectangle()
        pyautogui.scroll(clicks, x=rect.mid_point().x, y=rect.mid_point().y)
        return {"ok": True, "method": "mouse_scroll", "direction": direction}
```

**Step 3: Write `src/windowsagent/apps/file_explorer.py`**

```python
"""File Explorer app profile."""

from __future__ import annotations

import time

import pyautogui
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.apps.base import AppProfile


class FileExplorerProfile(AppProfile):
    name = "file_explorer"
    title_pattern = ""
    class_names = {"CabinetWClass"}

    def scroll(self, window: UIAWrapper, direction: str = "down", amount: int = 1) -> dict:
        """File Explorer: mouse scroll works on the file list."""
        clicks = -3 * amount if direction == "down" else 3 * amount
        rect = window.rectangle()
        pyautogui.scroll(clicks, x=rect.mid_point().x, y=rect.mid_point().y)
        return {"ok": True, "method": "mouse_scroll", "direction": direction}

    def navigate_to(self, window: UIAWrapper, target: str) -> dict:
        """Navigate to a folder via the address bar (much faster than clicking)."""
        # Click address bar — Ctrl+L is the shortcut
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.3)
        pyautogui.write(target, interval=0.02)
        pyautogui.press("enter")
        time.sleep(0.5)
        return {"ok": True, "method": "address_bar", "path": target}
```

**Step 4: Write `src/windowsagent/apps/outlook.py`**

```python
"""Outlook (new) app profile — WebView2 with virtualised lists."""

from __future__ import annotations

import time
from typing import Optional

import pyautogui
from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.apps.base import AppProfile
from windowsagent.webview2 import scroll_webview2, find_in_virtualised_list
from windowsagent.config import AgentConfig


class OutlookProfile(AppProfile):
    name = "outlook"
    title_pattern = "outlook"
    class_names = {"ApplicationFrameWindow"}

    @classmethod
    def matches(cls, window: UIAWrapper) -> bool:
        """Match new Outlook (WebView2-based)."""
        try:
            title = (window.element_info.name or "").lower()
            if "outlook" in title or "mail" in title:
                return True
        except Exception:
            pass
        return False

    def scroll(self, window: UIAWrapper, direction: str = "down", amount: int = 1) -> dict:
        """Outlook uses WebView2 — mouse scroll fails. Use Page Down/Up."""
        return scroll_webview2(window, direction=direction, pages=amount)

    def focus_panel(self, window: UIAWrapper, panel_name: str) -> dict:
        """Focus a specific Outlook panel.

        Outlook has: folder pane, message list, reading pane.
        Use F6 to cycle between panels.
        """
        panel_cycle_count = {
            "folder": 1,
            "message_list": 2,
            "reading": 3,
        }
        presses = panel_cycle_count.get(panel_name, 1)
        for _ in range(presses):
            pyautogui.press("f6")
            time.sleep(0.3)
        return {"ok": True, "method": "f6_cycle", "panel": panel_name}

    def find_email(
        self,
        window: UIAWrapper,
        subject: str,
        config: Optional[AgentConfig] = None,
    ) -> Optional[dict]:
        """Find an email by subject in the virtualised message list."""
        return find_in_virtualised_list(window, subject, config=config)
```

**Step 5: Update `src/windowsagent/apps/__init__.py`**

```python
"""App profiles - per-application automation strategies."""

from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.apps.base import AppProfile
from windowsagent.apps.notepad import NotepadProfile
from windowsagent.apps.file_explorer import FileExplorerProfile
from windowsagent.apps.outlook import OutlookProfile

_PROFILES: list[type[AppProfile]] = [
    OutlookProfile,
    FileExplorerProfile,
    NotepadProfile,
]


def detect_profile(window: UIAWrapper) -> AppProfile:
    """Detect which app profile matches a window.

    Returns the first matching profile, or a generic fallback.
    """
    for profile_cls in _PROFILES:
        if profile_cls.matches(window):
            return profile_cls()

    # Generic fallback: mouse scroll
    return _GenericProfile()


class _GenericProfile(AppProfile):
    """Fallback profile for unrecognised apps."""

    name = "generic"

    def scroll(self, window, direction="down", amount=1):
        import pyautogui
        clicks = -3 * amount if direction == "down" else 3 * amount
        rect = window.rectangle()
        pyautogui.scroll(clicks, x=rect.mid_point().x, y=rect.mid_point().y)
        return {"ok": True, "method": "generic_scroll", "direction": direction}
```

**Step 6: Write `tests/test_apps.py`**

```python
"""Tests for app profile detection."""

import pytest
from unittest.mock import MagicMock
from windowsagent.apps import detect_profile
from windowsagent.apps.notepad import NotepadProfile
from windowsagent.apps.file_explorer import FileExplorerProfile
from windowsagent.apps.outlook import OutlookProfile


def _mock_window(title: str, class_name: str) -> MagicMock:
    win = MagicMock()
    win.element_info.name = title
    win.element_info.class_name = class_name
    return win


class TestProfileDetection:
    def test_detects_notepad(self):
        win = _mock_window("Untitled - Notepad", "Notepad")
        profile = detect_profile(win)
        assert isinstance(profile, NotepadProfile)

    def test_detects_file_explorer(self):
        win = _mock_window("Documents", "CabinetWClass")
        profile = detect_profile(win)
        assert isinstance(profile, FileExplorerProfile)

    def test_detects_outlook(self):
        win = _mock_window("Outlook (new)", "ApplicationFrameWindow")
        profile = detect_profile(win)
        assert isinstance(profile, OutlookProfile)

    def test_generic_fallback(self):
        win = _mock_window("Some Random App", "SomeClass")
        profile = detect_profile(win)
        assert profile.name == "generic"

    def test_notepad_matches_windows_11_class(self):
        win = _mock_window("Untitled - Notepad", "ApplicationFrameWindow")
        # Windows 11 Notepad uses ApplicationFrameWindow but has "notepad" in title
        assert NotepadProfile.matches(win) is True
```

**Step 7: Run tests**

Run: `pytest tests/test_apps.py -v`
Expected: All 5 pass.

**Step 8: Commit**

```bash
git add src/windowsagent/apps/ tests/test_apps.py
git commit -m "feat: add app profiles for Notepad, File Explorer, and Outlook"
```

---

## Task 10: Agent Orchestrator

**Files:**
- Create: `src/windowsagent/agent.py`
- Create: `tests/test_agent.py`

**Step 1: Write `src/windowsagent/agent.py`**

This wires observe-act-verify into a single class. No LLM — the caller specifies actions directly. The agent handles the loop: observe, execute, verify.

```python
"""Main agent class — orchestrates observe-act-verify."""

from __future__ import annotations

from typing import Optional

from pywinauto.controls.uiawrapper import UIAWrapper

from windowsagent.config import AgentConfig
from windowsagent.observer.state import WindowState, observe_window
from windowsagent.observer.uia import connect_to_window, list_windows
from windowsagent.observer.screenshot import capture_window
from windowsagent.actor.uia_actor import UIAActor
from windowsagent.actor.input_actor import InputActor
from windowsagent.verifier.verify import Verifier
from windowsagent.apps import detect_profile
from windowsagent.apps.base import AppProfile


class Agent:
    """WindowsAgent — observe, act, verify on Windows desktop apps.

    Usage:
        agent = Agent()
        state = agent.observe("Notepad")
        agent.click(name="File", control_type="MenuItem")
        agent.type_text("Hello", control_type="Edit")
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.window: Optional[UIAWrapper] = None
        self.profile: Optional[AppProfile] = None
        self.uia_actor: Optional[UIAActor] = None
        self.input_actor = InputActor(self.config)
        self.verifier = Verifier(self.config)
        self.last_state: Optional[WindowState] = None

    def observe(
        self,
        title: Optional[str] = None,
        pid: Optional[int] = None,
        include_screenshot: bool = True,
    ) -> WindowState:
        """Observe a window's current state.

        Connects to the window, detects app profile, captures state.
        """
        self.window = connect_to_window(title=title, pid=pid)
        self.profile = detect_profile(self.window)
        self.uia_actor = UIAActor(self.window)
        self.last_state = observe_window(
            title=title, pid=pid,
            config=self.config,
            include_screenshot=include_screenshot,
        )
        return self.last_state

    def click(
        self,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        verify: Optional[bool] = None,
    ) -> dict:
        """Click an element. Tries UIA first, falls back to coordinates."""
        if verify is None:
            verify = self.config.verify_after_action

        before = capture_window(self.window) if verify else None

        # Coordinate click
        if x is not None and y is not None:
            result = self.input_actor.click(x, y)
        else:
            # UIA click
            self._ensure_connected()
            try:
                result = self.uia_actor.click(name, control_type, automation_id)
            except Exception:
                # Find element in last state for coordinate fallback
                if self.last_state:
                    el = self.last_state.find_element(
                        name=name, control_type=control_type, automation_id=automation_id,
                    )
                    if el:
                        rect = el["rect"]
                        result = self.input_actor.click(rect["mid_x"], rect["mid_y"])
                    else:
                        raise
                else:
                    raise

        if verify and before:
            result["verified"] = self.verifier.screenshot_changed(self.window, before)

        return result

    def type_text(
        self,
        text: str,
        name: Optional[str] = None,
        control_type: Optional[str] = None,
        automation_id: Optional[str] = None,
        clear_first: bool = False,
    ) -> dict:
        """Type text into a control."""
        self._ensure_connected()
        try:
            return self.uia_actor.type_text(
                text, name=name, control_type=control_type,
                automation_id=automation_id, clear_first=clear_first,
            )
        except Exception:
            # Fallback: type at current focus
            if clear_first:
                self.input_actor.hotkey("ctrl", "a")
                self.input_actor.press_key("delete")
            return self.input_actor.type_text(text)

    def press_key(self, key: str) -> dict:
        """Press a key."""
        return self.input_actor.press_key(key)

    def hotkey(self, *keys: str) -> dict:
        """Press a keyboard shortcut."""
        return self.input_actor.hotkey(*keys)

    def scroll(self, direction: str = "down", amount: int = 1) -> dict:
        """Scroll using the app profile's strategy."""
        self._ensure_connected()
        return self.profile.scroll(self.window, direction=direction, amount=amount)

    def get_windows(self) -> list[dict]:
        """List all visible windows."""
        return list_windows()

    def _ensure_connected(self) -> None:
        if self.window is None:
            raise RuntimeError("Call observe() first to connect to a window")
```

**Step 2: Write `tests/test_agent.py`**

```python
"""Tests for the main Agent class."""

import pytest
from windowsagent.agent import Agent


class TestAgentInit:
    def test_creates_with_defaults(self):
        agent = Agent()
        assert agent.window is None
        assert agent.config is not None

    def test_raises_if_no_observe_called(self):
        agent = Agent()
        with pytest.raises(RuntimeError, match="observe"):
            agent.click(name="Button")

    def test_get_windows_works_without_observe(self):
        agent = Agent()
        windows = agent.get_windows()
        assert isinstance(windows, list)


@pytest.mark.integration
class TestAgentNotepad:
    def test_observe_notepad(self):
        agent = Agent()
        state = agent.observe("Notepad")
        assert state.window_title is not None
        assert len(state.interactive_elements) > 0

    def test_type_and_verify(self):
        agent = Agent()
        agent.observe("Notepad")
        result = agent.type_text("Agent test", clear_first=True)
        assert result["ok"] is True
```

**Step 3: Run non-integration tests**

Run: `pytest tests/test_agent.py -v -m "not integration"`
Expected: 3 tests pass.

**Step 4: Commit**

```bash
git add src/windowsagent/agent.py tests/test_agent.py
git commit -m "feat: add Agent orchestrator with observe-act-verify loop"
```

---

## Task 11: HTTP API

**Files:**
- Create: `src/windowsagent/server.py`
- Create: `tests/test_server.py`

**Step 1: Write `src/windowsagent/server.py`**

Thin Flask layer over the Agent class. Matches the API spec from the brief.

```python
"""HTTP API for WindowsAgent — localhost service for OpenClaw integration."""

from __future__ import annotations

import traceback

from flask import Flask, jsonify, request

from windowsagent.agent import Agent
from windowsagent.config import AgentConfig

app = Flask(__name__)
agent = Agent()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "windowsagent", "version": "0.1.0"})


@app.route("/windows", methods=["GET"])
def get_windows():
    return jsonify({"windows": agent.get_windows()})


@app.route("/observe", methods=["POST"])
def observe():
    """Observe a window. Body: { "title": "...", "pid": 1234 }"""
    data = request.json or {}
    title = data.get("title")
    pid = data.get("pid")

    if not title and not pid:
        return jsonify({"error": "Provide title or pid"}), 400

    try:
        state = agent.observe(title=title, pid=pid)
        return jsonify({
            "window_title": state.window_title,
            "element_count": len(state.interactive_elements),
            "elements": state.interactive_elements,
            "control_tree": state.control_tree,
            "screenshot_b64": state.screenshot_b64,
        })
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/act", methods=["POST"])
def act():
    """Execute an action. Body: { "action": "click", ... }"""
    data = request.json or {}
    action = data.get("action")

    if not action:
        return jsonify({"error": "action required"}), 400

    try:
        if action == "click":
            result = agent.click(
                name=data.get("name"),
                control_type=data.get("control_type"),
                automation_id=data.get("automation_id"),
                x=data.get("x"),
                y=data.get("y"),
            )
        elif action == "type":
            result = agent.type_text(
                text=data.get("text", ""),
                name=data.get("name"),
                control_type=data.get("control_type"),
                automation_id=data.get("automation_id"),
                clear_first=data.get("clear_first", False),
            )
        elif action == "key":
            result = agent.press_key(data.get("key", ""))
        elif action == "hotkey":
            keys = data.get("keys", [])
            result = agent.hotkey(*keys)
        elif action == "scroll":
            result = agent.scroll(
                direction=data.get("direction", "down"),
                amount=data.get("amount", 1),
            )
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

        return jsonify(result)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/verify", methods=["POST"])
def verify():
    """Check current window state. Body: { "check": "element_exists", ... }"""
    data = request.json or {}
    check = data.get("check")

    if not check:
        return jsonify({"error": "check required"}), 400

    try:
        if check == "element_exists":
            exists = agent.verifier.element_appeared(
                agent.window,
                name=data.get("name"),
                control_type=data.get("control_type"),
            )
            return jsonify({"exists": exists})
        else:
            return jsonify({"error": f"Unknown check: {check}"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.errorhandler(Exception)
def handle_error(exc):
    return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


def run_server(host: str = "127.0.0.1", port: int = 7862):
    """Start the HTTP API server."""
    print(f"WindowsAgent API running on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
```

**Step 2: Write `tests/test_server.py`**

```python
"""Tests for the HTTP API."""

import pytest
from windowsagent.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "windowsagent"


class TestWindowsEndpoint:
    def test_lists_windows(self, client):
        response = client.get("/windows")
        assert response.status_code == 200
        data = response.get_json()
        assert "windows" in data
        assert isinstance(data["windows"], list)


class TestObserveEndpoint:
    def test_requires_title_or_pid(self, client):
        response = client.post("/observe", json={})
        assert response.status_code == 400

    def test_returns_404_for_nonexistent_window(self, client):
        response = client.post("/observe", json={"title": "NonexistentWindow99999"})
        assert response.status_code == 404


class TestActEndpoint:
    def test_requires_action(self, client):
        response = client.post("/act", json={})
        assert response.status_code == 400

    def test_unknown_action(self, client):
        response = client.post("/act", json={"action": "dance"})
        assert response.status_code == 400
```

**Step 3: Run tests**

Run: `pytest tests/test_server.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/windowsagent/server.py tests/test_server.py
git commit -m "feat: add Flask HTTP API with observe/act/verify endpoints"
```

---

## Task 12: CLI

**Files:**
- Create: `src/windowsagent/cli.py`

**Step 1: Write `src/windowsagent/cli.py`**

```python
"""Command-line interface for WindowsAgent."""

from __future__ import annotations

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="windowsagent",
        description="AI desktop automation for Windows",
    )
    subparsers = parser.add_subparsers(dest="command")

    # windowsagent windows
    subparsers.add_parser("windows", help="List visible windows")

    # windowsagent observe
    obs = subparsers.add_parser("observe", help="Observe a window's state")
    obs.add_argument("--window", "-w", required=True, help="Window title to observe")
    obs.add_argument("--screenshot", action="store_true", help="Include screenshot")

    # windowsagent act
    act = subparsers.add_parser("act", help="Execute an action")
    act.add_argument("--window", "-w", required=True, help="Window title")
    act.add_argument("--action", "-a", required=True, choices=["click", "type", "key", "scroll"])
    act.add_argument("--name", help="Control name")
    act.add_argument("--type", dest="control_type", help="Control type")
    act.add_argument("--text", help="Text to type")
    act.add_argument("--key", help="Key to press")

    # windowsagent serve
    srv = subparsers.add_parser("serve", help="Start HTTP API server")
    srv.add_argument("--port", type=int, default=7862, help="Port (default 7862)")
    srv.add_argument("--host", default="127.0.0.1", help="Host (default 127.0.0.1)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "windows":
        _cmd_windows()
    elif args.command == "observe":
        _cmd_observe(args)
    elif args.command == "act":
        _cmd_act(args)
    elif args.command == "serve":
        _cmd_serve(args)


def _cmd_windows():
    from windowsagent.agent import Agent
    agent = Agent()
    windows = agent.get_windows()
    print(json.dumps(windows, indent=2))


def _cmd_observe(args):
    from windowsagent.agent import Agent
    agent = Agent()
    state = agent.observe(title=args.window, include_screenshot=args.screenshot)
    output = {
        "window_title": state.window_title,
        "element_count": len(state.interactive_elements),
        "elements": state.interactive_elements,
    }
    print(json.dumps(output, indent=2))


def _cmd_act(args):
    from windowsagent.agent import Agent
    agent = Agent()
    agent.observe(title=args.window)

    if args.action == "click":
        result = agent.click(name=args.name, control_type=args.control_type)
    elif args.action == "type":
        result = agent.type_text(args.text or "", control_type=args.control_type)
    elif args.action == "key":
        result = agent.press_key(args.key or "")
    elif args.action == "scroll":
        result = agent.scroll()
    else:
        result = {"error": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))


def _cmd_serve(args):
    from windowsagent.server import run_server
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add src/windowsagent/cli.py
git commit -m "feat: add CLI with windows/observe/act/serve commands"
```

---

## Task 13: Update Package Exports + Final README

**Files:**
- Modify: `src/windowsagent/__init__.py`
- Modify: `README.md`

**Step 1: Update `src/windowsagent/__init__.py`**

```python
"""WindowsAgent - AI desktop automation for Windows."""

__version__ = "0.1.0"

from windowsagent.agent import Agent
from windowsagent.config import AgentConfig

__all__ = ["Agent", "AgentConfig"]
```

**Step 2: Update `README.md` with usage examples**

Add a Quick Start section showing:
```python
from windowsagent import Agent

agent = Agent()
state = agent.observe("Notepad")
print(f"Found {len(state.interactive_elements)} interactive elements")

agent.type_text("Hello from WindowsAgent!", clear_first=True)
agent.hotkey("ctrl", "s")
```

And CLI usage:
```bash
windowsagent windows
windowsagent observe --window "Notepad"
windowsagent act --window "Notepad" --action type --text "Hello"
windowsagent serve --port 7862
```

**Step 3: Run full test suite**

Run: `pytest tests/ -v -m "not integration"`
Expected: All unit tests pass.

**Step 4: Run integration tests (open Notepad first)**

Run: `pytest tests/ -v -m integration`
Expected: Notepad tests pass.

**Step 5: Commit**

```bash
git add src/windowsagent/__init__.py README.md
git commit -m "feat: finalise package exports and update README with usage"
```

---

## Summary

| Task | What it builds | Files | Tests |
|------|---------------|-------|-------|
| 1 | Git + scaffold | pyproject.toml, config, directory structure | 0 (setup) |
| 2 | UIA observer | observer/uia.py | 5 unit + 3 integration |
| 3 | Screenshot capture | observer/screenshot.py | 6 unit |
| 4 | Combined state | observer/state.py | 5 unit |
| 5 | UIA actor | actor/uia_actor.py | 1 unit + 2 integration |
| 6 | Input fallback | actor/input_actor.py | 2 unit |
| 7 | WebView2 handler | webview2.py | 4 unit |
| 8 | Verifier | verifier/verify.py | 2 unit |
| 9 | App profiles | apps/*.py | 5 unit |
| 10 | Agent orchestrator | agent.py | 3 unit + 2 integration |
| 11 | HTTP API | server.py | 6 unit |
| 12 | CLI | cli.py | 0 (manual test) |
| 13 | Exports + README | __init__.py, README.md | Full suite run |

**Total: 13 tasks, 13 commits, ~39 unit tests, ~7 integration tests**

## After Phase 1

Phase 2 adds:
- Task planner (LLM-based task decomposition)
- Vision grounder (Gemini Flash / Claude Haiku for screenshot analysis)
- OCR module (Windows OCR API)
- More app profiles (Excel, Teams, Chrome/Edge)
- OpenClaw skill definition
