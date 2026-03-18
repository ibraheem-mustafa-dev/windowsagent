"""
Private capture backend implementations for WindowsAgent screenshot module.

These functions are implementation details of screenshot.py and should not
be imported directly by external code.
"""

from __future__ import annotations

import logging
import ctypes
import ctypes.wintypes
import time
from typing import TYPE_CHECKING

from windowsagent.exceptions import ScreenshotError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.screenshot import Screenshot

logger = logging.getLogger(__name__)


def _capture_mss_full(config: Config) -> Screenshot:
    """Capture full virtual desktop using mss."""
    from windowsagent.observer.screenshot import Screenshot, get_dpi_scale

    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise ScreenshotError("mss or Pillow not installed") from exc

    dpi = get_dpi_scale()
    timestamp = time.time()

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # index 0 = all monitors
            raw = sct.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            physical_w, physical_h = raw.size
            logical_w = int(physical_w / dpi)
            logical_h = int(physical_h / dpi)
            return Screenshot(
                image=image,
                dpi_scale=dpi,
                timestamp=timestamp,
                monitor_index=0,
                logical_width=logical_w,
                logical_height=logical_h,
                physical_width=physical_w,
                physical_height=physical_h,
            )
    except Exception as exc:
        raise ScreenshotError(f"mss full capture failed: {exc}") from exc


def _capture_mss_monitor(monitor_index: int, config: Config) -> Screenshot:
    """Capture a specific monitor using mss."""
    from windowsagent.observer.screenshot import Screenshot, get_dpi_scale

    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise ScreenshotError("mss or Pillow not installed") from exc

    dpi = get_dpi_scale()
    timestamp = time.time()

    try:
        with mss.mss() as sct:
            if monitor_index >= len(sct.monitors):
                raise ScreenshotError(
                    f"Monitor index {monitor_index} out of range "
                    f"(available: 1-{len(sct.monitors) - 1})"
                )
            monitor = sct.monitors[monitor_index]
            raw = sct.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            physical_w, physical_h = raw.size
            logical_w = int(physical_w / dpi)
            logical_h = int(physical_h / dpi)
            return Screenshot(
                image=image,
                dpi_scale=dpi,
                timestamp=timestamp,
                monitor_index=monitor_index,
                logical_width=logical_w,
                logical_height=logical_h,
                physical_width=physical_w,
                physical_height=physical_h,
            )
    except ScreenshotError:
        raise
    except Exception as exc:
        raise ScreenshotError(f"mss monitor capture failed: {exc}") from exc


def _capture_mss_region(
    left: int,
    top: int,
    width: int,
    height: int,
    hwnd: int,
    dpi: float,
) -> Screenshot:
    """Capture a rectangular region using mss."""
    from windowsagent.observer.screenshot import Screenshot

    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        raise ScreenshotError("mss or Pillow not installed") from exc

    timestamp = time.time()

    try:
        with mss.mss() as sct:
            region = {"left": left, "top": top, "width": width, "height": height}
            raw = sct.grab(region)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            physical_w, physical_h = raw.size
            return Screenshot(
                image=image,
                dpi_scale=dpi,
                timestamp=timestamp,
                monitor_index=0,
                logical_width=width,
                logical_height=height,
                physical_width=physical_w,
                physical_height=physical_h,
                hwnd=hwnd,
            )
    except Exception as exc:
        raise ScreenshotError(f"mss region capture failed: {exc}") from exc


def _capture_pyautogui_full(config: Config) -> Screenshot:
    """Capture full screen using pyautogui as fallback."""
    from windowsagent.observer.screenshot import Screenshot, get_dpi_scale

    try:
        import pyautogui
    except ImportError as exc:
        raise ScreenshotError("pyautogui not installed") from exc

    dpi = get_dpi_scale()
    timestamp = time.time()

    try:
        image = pyautogui.screenshot()
        physical_w, physical_h = image.size
        logical_w = int(physical_w / dpi)
        logical_h = int(physical_h / dpi)
        return Screenshot(
            image=image,
            dpi_scale=dpi,
            timestamp=timestamp,
            monitor_index=0,
            logical_width=logical_w,
            logical_height=logical_h,
            physical_width=physical_w,
            physical_height=physical_h,
        )
    except Exception as exc:
        raise ScreenshotError(f"pyautogui screenshot failed: {exc}") from exc


def _capture_pyautogui_region(
    left: int,
    top: int,
    width: int,
    height: int,
    hwnd: int,
    dpi: float,
) -> Screenshot:
    """Capture a rectangular region using pyautogui."""
    from windowsagent.observer.screenshot import Screenshot

    try:
        import pyautogui
    except ImportError as exc:
        raise ScreenshotError("pyautogui not installed") from exc

    timestamp = time.time()

    try:
        image = pyautogui.screenshot(region=(left, top, width, height))
        physical_w, physical_h = image.size
        return Screenshot(
            image=image,
            dpi_scale=dpi,
            timestamp=timestamp,
            monitor_index=0,
            logical_width=width,
            logical_height=height,
            physical_width=physical_w,
            physical_height=physical_h,
            hwnd=hwnd,
        )
    except Exception as exc:
        raise ScreenshotError(f"pyautogui region capture failed: {exc}") from exc


def _get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return (left, top, right, bottom) for a window in logical pixels.

    Uses GetWindowRect which returns screen coordinates in logical pixels on
    DPI-aware processes.
    """
    try:
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except (AttributeError, OSError) as exc:
        logger.debug("GetWindowRect failed for HWND %d: %s", hwnd, exc)
    return None
