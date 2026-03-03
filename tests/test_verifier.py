"""
Tests for the verifier module.

Tests the screenshot diff algorithm and wait_for_change polling.
Most tests are unit tests — only integration tests open real apps.
"""

from __future__ import annotations

import time

import pytest
from PIL import Image


def _make_screenshot(
    color: tuple[int, int, int] = (128, 128, 128),
    width: int = 200,
    height: int = 150,
) -> "object":
    """Create a test Screenshot with a solid colour."""
    from windowsagent.observer.screenshot import Screenshot

    img = Image.new("RGB", (width, height), color=color)
    return Screenshot(
        image=img,
        dpi_scale=1.0,
        timestamp=time.time(),
        monitor_index=0,
        logical_width=width,
        logical_height=height,
        physical_width=width,
        physical_height=height,
    )


class TestScreenshotDiff:
    """Tests for verifier/verify.py screenshot_diff()"""

    def test_identical_screenshots_return_zero(self) -> None:
        """Diff of the exact same screenshot should be 0.0."""
        from windowsagent.verifier.verify import screenshot_diff

        sc = _make_screenshot(color=(100, 150, 200))
        result = screenshot_diff(sc, sc)
        assert result == 0.0

    def test_same_content_different_objects_returns_zero(self) -> None:
        """Two screenshots with identical pixel data should diff as 0.0."""
        from windowsagent.verifier.verify import screenshot_diff

        sc1 = _make_screenshot(color=(50, 100, 150))
        sc2 = _make_screenshot(color=(50, 100, 150))
        result = screenshot_diff(sc1, sc2)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_completely_different_returns_high_diff(self) -> None:
        """Black vs white screenshot should return a high diff value."""
        from windowsagent.verifier.verify import screenshot_diff

        black = _make_screenshot(color=(0, 0, 0))
        white = _make_screenshot(color=(255, 255, 255))
        result = screenshot_diff(black, white)
        assert result > 0.9  # Should be close to 1.0

    def test_small_change_returns_small_diff(self) -> None:
        """Changing one pixel should return a very small diff."""
        from windowsagent.verifier.verify import screenshot_diff
        from PIL import Image

        from windowsagent.observer.screenshot import Screenshot

        img1 = Image.new("RGB", (100, 100), color=(128, 128, 128))
        img2 = img1.copy()
        img2.putpixel((50, 50), (255, 0, 0))  # Change one pixel

        sc1 = Screenshot(
            image=img1,
            dpi_scale=1.0,
            timestamp=time.time(),
            monitor_index=0,
            logical_width=100,
            logical_height=100,
            physical_width=100,
            physical_height=100,
        )
        sc2 = Screenshot(
            image=img2,
            dpi_scale=1.0,
            timestamp=time.time(),
            monitor_index=0,
            logical_width=100,
            logical_height=100,
            physical_width=100,
            physical_height=100,
        )

        result = screenshot_diff(sc1, sc2)
        assert 0.0 < result < 0.01  # Small but non-zero

    def test_diff_is_symmetric(self) -> None:
        """diff(a, b) should equal diff(b, a)."""
        from windowsagent.verifier.verify import screenshot_diff

        sc1 = _make_screenshot(color=(100, 0, 0))
        sc2 = _make_screenshot(color=(0, 100, 0))
        assert screenshot_diff(sc1, sc2) == pytest.approx(screenshot_diff(sc2, sc1), abs=1e-6)

    def test_diff_handles_different_sizes(self) -> None:
        """Diff of different-sized screenshots should not raise."""
        from windowsagent.verifier.verify import screenshot_diff

        sc1 = _make_screenshot(width=100, height=100)
        sc2 = _make_screenshot(width=200, height=150)
        result = screenshot_diff(sc1, sc2)
        assert 0.0 <= result <= 1.0

    def test_diff_result_in_range(self) -> None:
        """screenshot_diff result must always be in [0.0, 1.0]."""
        from windowsagent.verifier.verify import screenshot_diff

        sc1 = _make_screenshot(color=(0, 0, 0))
        sc2 = _make_screenshot(color=(255, 255, 255))
        result = screenshot_diff(sc1, sc2)
        assert 0.0 <= result <= 1.0


class TestUIAElementChanged:
    """Tests for verifier/verify.py uia_element_changed()"""

    def _make_elem(self, name: str = "A", value: str = "", enabled: bool = True) -> "object":
        from windowsagent.observer.uia import UIAElement
        return UIAElement(
            name=name,
            control_type="Button",
            automation_id="",
            class_name="",
            rect=(0, 0, 100, 50),
            is_enabled=enabled,
            is_visible=True,
            patterns=[],
            value=value,
        )

    def test_same_element_not_changed(self) -> None:
        from windowsagent.verifier.verify import uia_element_changed
        elem = self._make_elem(name="Submit", value="")
        assert uia_element_changed(elem, elem) is False

    def test_value_change_detected(self) -> None:
        from windowsagent.verifier.verify import uia_element_changed
        before = self._make_elem(value="")
        after = self._make_elem(value="hello")
        assert uia_element_changed(before, after) is True

    def test_name_change_detected(self) -> None:
        from windowsagent.verifier.verify import uia_element_changed
        before = self._make_elem(name="Submit")
        after = self._make_elem(name="Submitting...")
        assert uia_element_changed(before, after) is True

    def test_enabled_change_detected(self) -> None:
        from windowsagent.verifier.verify import uia_element_changed
        before = self._make_elem(enabled=False)
        after = self._make_elem(enabled=True)
        assert uia_element_changed(before, after) is True


@pytest.mark.integration
class TestWaitForChangeIntegration:
    """Integration tests for wait_for_change — require Windows."""

    @pytest.fixture(autouse=True)
    def open_notepad(self):
        import subprocess
        import time
        proc = subprocess.Popen(["notepad.exe"])
        time.sleep(1.5)
        yield proc
        try:
            proc.terminate()
        except Exception:
            pass

    def test_wait_for_change_detects_typing(self) -> None:
        """wait_for_change should return True when text is typed in Notepad."""
        import threading
        import time
        from windowsagent.config import load_config
        from windowsagent.observer.uia import get_windows
        from windowsagent.verifier.verify import wait_for_change
        from windowsagent.actor.input_actor import type_text

        config = load_config()

        # Find Notepad HWND
        windows = get_windows()
        notepad_wins = [w for w in windows if "notepad" in w.title.lower()]
        if not notepad_wins:
            pytest.skip("Notepad window not found")

        hwnd = notepad_wins[0].hwnd

        # Type after a short delay in a background thread
        def _type_delayed() -> None:
            time.sleep(0.5)
            type_text("Testing wait_for_change")

        t = threading.Thread(target=_type_delayed)
        t.start()

        result = wait_for_change(hwnd, config, timeout=3.0)
        t.join()

        assert result is True

    def test_wait_for_change_times_out_when_no_action(self) -> None:
        """wait_for_change should return False when nothing changes."""
        from windowsagent.config import Config
        from windowsagent.observer.uia import get_windows
        from windowsagent.verifier.verify import wait_for_change

        # Use a very short timeout
        config = Config(verify_timeout=0.5)

        windows = get_windows()
        notepad_wins = [w for w in windows if "notepad" in w.title.lower()]
        if not notepad_wins:
            pytest.skip("Notepad window not found")

        hwnd = notepad_wins[0].hwnd
        result = wait_for_change(hwnd, config, timeout=0.5)
        # Should return False because nothing is happening
        assert result is False
