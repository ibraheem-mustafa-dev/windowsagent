"""
Screenshot capture module for WindowsAgent.

Primary backend: mss (fastest, ~10ms per full capture)
Fallback backend: pyautogui

Handles DPI awareness and multi-monitor setups. All coordinates are in logical
pixels; physical dimensions are also stored for vision model use.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import ScreenshotError

if TYPE_CHECKING:
    from windowsagent.config import Config

logger = logging.getLogger(__name__)

# Windows DPI awareness constants
MDT_EFFECTIVE_DPI = 0

# Try to enable per-monitor DPI awareness at import time
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


@dataclass
class MonitorInfo:
    """Information about a single monitor."""

    index: int                               # 1-based monitor index (mss convention)
    left: int                                # left edge in logical pixels
    top: int                                 # top edge in logical pixels
    width: int                               # width in logical pixels
    height: int                              # height in logical pixels
    is_primary: bool = False


@dataclass
class Screenshot:
    """A captured screenshot with metadata.

    All dimension/position values are in logical pixels unless suffixed with
    _physical, which indicates raw device pixels.
    """

    image: Any                               # PIL.Image.Image (typed as Any to avoid hard dep)
    dpi_scale: float                         # e.g. 1.5 for 150% scaling
    timestamp: float                         # time.time() at moment of capture
    monitor_index: int                       # 0 = all monitors, 1+ = specific monitor
    logical_width: int
    logical_height: int
    physical_width: int
    physical_height: int
    hwnd: int = 0                            # HWND if captured from specific window, else 0


def get_dpi_scale(hwnd: int = 0) -> float:
    """Return the DPI scale factor for a window or the primary monitor.

    Args:
        hwnd: Window handle. If 0, uses primary monitor DPI.

    Returns:
        Scale factor as a float. 1.0 = 96 DPI (100%), 1.5 = 144 DPI (150%).
    """
    try:
        if hwnd:
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            if dpi > 0:
                return float(dpi / 96.0)
    except (AttributeError, OSError):
        pass

    try:
        # Fallback: query primary monitor DPI
        hdc = ctypes.windll.user32.GetDC(0)
        dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi_x > 0:
            return float(dpi_x / 96.0)
    except (AttributeError, OSError):
        pass

    logger.debug("Could not determine DPI, defaulting to 1.0")
    return 1.0


def list_monitors() -> list[MonitorInfo]:
    """Return information about all connected monitors.

    Returns:
        List of MonitorInfo, one per monitor. Index matches mss convention (1-based).
    """
    try:
        import mss

        with mss.mss() as sct:
            monitors = []
            for idx, mon in enumerate(sct.monitors):
                if idx == 0:
                    # mss index 0 is the virtual screen (all monitors combined); skip here
                    continue
                monitors.append(
                    MonitorInfo(
                        index=idx,
                        left=mon["left"],
                        top=mon["top"],
                        width=mon["width"],
                        height=mon["height"],
                        is_primary=(idx == 1),
                    )
                )
            return monitors
    except ImportError:
        logger.warning("mss not available; list_monitors returning empty list")
        return []
    except Exception as exc:
        logger.warning("list_monitors failed: %s", exc)
        return []


def capture_full(config: Config) -> Screenshot:
    """Capture the full virtual desktop (all monitors combined).

    Args:
        config: WindowsAgent configuration.

    Returns:
        Screenshot of the entire virtual desktop.

    Raises:
        ScreenshotError: If capture fails with both backends.
    """
    if config.screenshot_backend == "mss":
        try:
            return _capture_mss_full(config)
        except ScreenshotError:
            raise
        except Exception as exc:
            logger.warning("mss full capture failed: %s — trying pyautogui", exc)

    return _capture_pyautogui_full(config)


def capture_monitor(monitor_index: int, config: Config) -> Screenshot:
    """Capture a specific monitor.

    Args:
        monitor_index: 1-based monitor index.
        config: WindowsAgent configuration.

    Returns:
        Screenshot of the specified monitor.

    Raises:
        ScreenshotError: If the monitor index is invalid or capture fails.
    """
    if config.screenshot_backend == "mss":
        try:
            return _capture_mss_monitor(monitor_index, config)
        except ScreenshotError:
            raise
        except Exception as exc:
            logger.warning("mss monitor capture failed: %s — trying pyautogui", exc)

    return _capture_pyautogui_full(config)


def capture_window(hwnd: int, config: Config) -> Screenshot:
    """Capture a specific window by its handle.

    Falls back to capturing the full screen if the window region cannot be
    determined cleanly.

    Args:
        hwnd: Native window handle.
        config: WindowsAgent configuration.

    Returns:
        Screenshot cropped to the window's bounding rectangle.

    Raises:
        ScreenshotError: If capture fails.
    """
    try:
        rect = _get_window_rect(hwnd)
        if rect is None:
            logger.warning("Could not get rect for HWND %d, capturing full screen", hwnd)
            return capture_full(config)

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            logger.warning("Invalid window rect for HWND %d, capturing full screen", hwnd)
            return capture_full(config)

        dpi = get_dpi_scale(hwnd)

        if config.screenshot_backend == "mss":
            try:
                return _capture_mss_region(left, top, width, height, hwnd, dpi)
            except Exception as exc:
                logger.warning("mss window capture failed: %s — trying pyautogui", exc)

        return _capture_pyautogui_region(left, top, width, height, hwnd, dpi)

    except Exception as exc:
        raise ScreenshotError(f"Window capture failed for HWND {hwnd}: {exc}") from exc


# ── Private helpers ──────────────────────────────────────────────────────────


def _capture_mss_full(config: Config) -> Screenshot:
    """Capture full virtual desktop using mss."""
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
