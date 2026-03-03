"""
Tests for the observer module.

Unit tests that do not require real Windows applications run immediately.
Integration tests (marked with pytest.mark.integration) require Windows
and open actual applications.

Run unit tests only:
    pytest tests/test_observer.py -m "not integration" -v

Run all observer tests (Windows only):
    pytest tests/test_observer.py -v
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


# ── Unit tests (no real Windows apps) ────────────────────────────────────────


class TestScreenshot:
    """Tests for observer/screenshot.py"""

    def test_get_dpi_scale_returns_positive_float(self) -> None:
        """DPI scale should always be a positive float."""
        from windowsagent.observer.screenshot import get_dpi_scale
        scale = get_dpi_scale()
        assert isinstance(scale, float)
        assert scale > 0.0
        # Typical range: 1.0 (100%) to 2.0 (200%) — allow wider range for test machines
        assert 0.5 <= scale <= 4.0

    def test_list_monitors_returns_list(self) -> None:
        """list_monitors should return a list (may be empty in CI without a display)."""
        from windowsagent.observer.screenshot import list_monitors
        monitors = list_monitors()
        assert isinstance(monitors, list)

    def test_screenshot_dataclass_fields(self) -> None:
        """Screenshot dataclass should have all required fields."""
        from windowsagent.observer.screenshot import Screenshot
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        sc = Screenshot(
            image=img,
            dpi_scale=1.0,
            timestamp=time.time(),
            monitor_index=0,
            logical_width=100,
            logical_height=100,
            physical_width=100,
            physical_height=100,
        )
        assert sc.dpi_scale == 1.0
        assert sc.logical_width == 100
        assert sc.monitor_index == 0


@pytest.mark.integration
class TestScreenshotIntegration:
    """Integration tests — require a display."""

    def test_capture_full_returns_screenshot(self) -> None:
        """Full desktop capture should return a valid Screenshot."""
        from windowsagent.config import load_config
        from windowsagent.observer.screenshot import capture_full

        config = load_config()
        sc = capture_full(config)

        assert sc.image is not None
        assert sc.logical_width > 0
        assert sc.logical_height > 0
        assert sc.dpi_scale > 0.0
        assert sc.timestamp > 0.0
        assert sc.monitor_index == 0

    def test_capture_full_image_dimensions_match(self) -> None:
        """Captured image dimensions should match reported dimensions."""
        from windowsagent.config import load_config
        from windowsagent.observer.screenshot import capture_full

        config = load_config()
        sc = capture_full(config)

        assert sc.physical_width == sc.image.width
        assert sc.physical_height == sc.image.height


# ── UIAElement tests ──────────────────────────────────────────────────────────


class TestUIAElement:
    """Tests for observer/uia.py UIAElement"""

    def test_centre_calculation(self) -> None:
        """Centre property should return the midpoint of the bounding rect."""
        from windowsagent.observer.uia import UIAElement

        elem = UIAElement(
            name="Test",
            control_type="Button",
            automation_id="",
            class_name="",
            rect=(100, 200, 300, 400),
            is_enabled=True,
            is_visible=True,
            patterns=[],
            value="",
        )
        cx, cy = elem.centre
        assert cx == 200  # (100 + 300) // 2
        assert cy == 300  # (200 + 400) // 2

    def test_is_interactable_with_patterns(self) -> None:
        """is_interactable should be True when patterns exist and element is enabled/visible."""
        from windowsagent.observer.uia import UIAElement

        elem = UIAElement(
            name="Button",
            control_type="Button",
            automation_id="",
            class_name="",
            rect=(0, 0, 100, 50),
            is_enabled=True,
            is_visible=True,
            patterns=["invoke"],
            value="",
        )
        assert elem.is_interactable is True

    def test_is_interactable_false_when_disabled(self) -> None:
        """is_interactable should be False for disabled elements."""
        from windowsagent.observer.uia import UIAElement

        elem = UIAElement(
            name="Button",
            control_type="Button",
            automation_id="",
            class_name="",
            rect=(0, 0, 100, 50),
            is_enabled=False,
            is_visible=True,
            patterns=["invoke"],
            value="",
        )
        assert elem.is_interactable is False


class TestFindElement:
    """Tests for observer/uia.py find_element()"""

    def _make_tree(self) -> "object":
        """Build a minimal UIATree for testing."""
        from windowsagent.observer.uia import UIAElement, UIATree

        child1 = UIAElement(
            name="File",
            control_type="MenuItem",
            automation_id="menu_file",
            class_name="",
            rect=(10, 10, 100, 30),
            is_enabled=True,
            is_visible=True,
            patterns=["invoke"],
            value="",
            depth=1,
        )
        child2 = UIAElement(
            name="Send",
            control_type="Button",
            automation_id="btn_send",
            class_name="",
            rect=(200, 400, 300, 450),
            is_enabled=True,
            is_visible=True,
            patterns=["invoke"],
            value="",
            depth=1,
        )
        edit = UIAElement(
            name="Subject",
            control_type="Edit",
            automation_id="txt_subject",
            class_name="",
            rect=(50, 100, 600, 130),
            is_enabled=True,
            is_visible=True,
            patterns=["value"],
            value="Test email",
            depth=1,
        )
        root = UIAElement(
            name="My Window",
            control_type="Window",
            automation_id="",
            class_name="",
            rect=(0, 0, 800, 600),
            is_enabled=True,
            is_visible=True,
            patterns=[],
            value="",
            children=[child1, child2, edit],
            depth=0,
        )
        return UIATree(
            root=root,
            window_title="My Window",
            app_name="test.exe",
            timestamp=time.time(),
            pid=0,
            hwnd=0,
        )

    def test_find_by_automation_id(self) -> None:
        """find_element should find exact automation_id match."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, automation_id="btn_send")
        assert result is not None
        assert result.name == "Send"

    def test_find_by_name_and_type(self) -> None:
        """find_element should find by name + control_type."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, name="File", control_type="MenuItem")
        assert result is not None
        assert result.automation_id == "menu_file"

    def test_find_by_name_only(self) -> None:
        """find_element should find by name alone."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, name="Send")
        assert result is not None
        assert result.control_type == "Button"

    def test_find_by_value(self) -> None:
        """find_element should find elements by value content."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, value="Test email")
        assert result is not None
        assert result.name == "Subject"

    def test_find_returns_none_for_missing(self) -> None:
        """find_element should return None when no element matches."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, name="NonExistentElement")
        assert result is None

    def test_find_case_insensitive(self) -> None:
        """find_element should match names case-insensitively."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree, name="send")
        assert result is not None
        assert result.name == "Send"

    def test_find_with_no_criteria_returns_none(self) -> None:
        """find_element with no criteria should return None."""
        from windowsagent.observer.uia import find_element
        tree = self._make_tree()
        result = find_element(tree)
        assert result is None


# ── Integration tests (require Windows) ──────────────────────────────────────


@pytest.mark.integration
class TestUIAIntegration:
    """Integration tests that require a real Windows desktop."""

    def test_get_windows_returns_non_empty(self) -> None:
        """get_windows should return at least one visible window on a running desktop."""
        from windowsagent.observer.uia import get_windows

        windows = get_windows()
        assert isinstance(windows, list)
        assert len(windows) > 0, "Expected at least one visible window"

    def test_window_info_has_required_fields(self) -> None:
        """Each WindowInfo should have title, app_name, pid, hwnd."""
        from windowsagent.observer.uia import get_windows

        windows = get_windows()
        for win in windows:
            assert win.title, f"Window has empty title: {win}"
            assert win.hwnd > 0, f"Window has invalid HWND: {win}"
            assert win.pid >= 0


@pytest.mark.integration
class TestStateCaptureIntegration:
    """Integration tests for state.py — require Notepad to be available."""

    @pytest.fixture(autouse=True)
    def open_notepad(self) -> "object":
        """Open Notepad before each test, close after."""
        import subprocess
        import time
        proc = subprocess.Popen(["notepad.exe"])
        time.sleep(1.5)  # Wait for window
        yield proc
        try:
            proc.terminate()
        except Exception:
            pass

    def test_capture_notepad_state(self) -> None:
        """capture() should return a valid AppState for Notepad."""
        from windowsagent.config import load_config
        from windowsagent.observer.state import capture

        config = load_config()
        state = capture("Notepad", config)

        assert state.window_title
        assert "notepad" in state.window_title.lower() or "untitled" in state.window_title.lower()
        assert state.screenshot is not None
        assert state.uia_tree is not None
        assert state.hwnd > 0
