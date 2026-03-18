"""
Window Manager — cross-platform window lifecycle operations via pywinctl.

Provides a clean abstraction over pywinctl for window activation, state
management, positioning, and enumeration. This replaces scattered ctypes
and win32gui calls throughout the codebase with a single entry point.

Why pywinctl over raw win32gui:
- Cross-platform potential (macOS/Linux support)
- Higher-level API (activate vs SetForegroundWindow + ShowWindow + SW_RESTORE)
- Built-in wait parameter for state transitions
- Window alive checks and z-order control
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from windowsagent.exceptions import WindowNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class WindowGeometry:
    """Window position and size in logical pixels."""

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def centre(self) -> tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)


def _get_pywinctl() -> Any:
    """Import pywinctl, raising a clear error if not installed."""
    try:
        import pywinctl
        return pywinctl
    except ImportError as exc:
        raise ImportError(
            "pywinctl is required for window management. "
            "Install with: pip install pywinctl>=0.4"
        ) from exc


def get_active_window() -> Any | None:
    """Return the currently focused window, or None if no window is focused."""
    pwc = _get_pywinctl()
    return pwc.getActiveWindow()


def get_all_windows() -> list[Any]:
    """Return all visible windows as pywinctl Window objects."""
    pwc = _get_pywinctl()
    result: list[Any] = pwc.getAllWindows()
    return result


def get_all_titles() -> list[str]:
    """Return titles of all visible windows."""
    pwc = _get_pywinctl()
    result: list[str] = list(pwc.getAllTitles())
    return result


def find_windows(title: str) -> list[Any]:
    """Find windows whose title contains the given substring (case-insensitive).

    Args:
        title: Substring to match against window titles.

    Returns:
        List of matching pywinctl Window objects.
    """
    pwc = _get_pywinctl()
    try:
        matches = pwc.getWindowsWithTitle(title)
        return list(matches) if matches else []
    except Exception:
        # Fallback: manual substring search
        return [w for w in pwc.getAllWindows() if title.lower() in w.title.lower()]


def find_window(title: str) -> Any:
    """Find a single window by title substring. Raises if not found.

    Args:
        title: Substring to match against window titles.

    Returns:
        First matching pywinctl Window object.

    Raises:
        WindowNotFoundError: If no matching window exists.
    """
    matches = find_windows(title)
    if not matches:
        raise WindowNotFoundError(title)
    return matches[0]


def get_window_by_hwnd(hwnd: int) -> Any | None:
    """Find a window by its native handle.

    Args:
        hwnd: Native window handle (HWND on Windows).

    Returns:
        pywinctl Window object, or None if not found.
    """
    pwc = _get_pywinctl()
    for win in pwc.getAllWindows():
        if win.getHandle() == hwnd:
            return win
    return None


def activate(window: Any, wait: bool = True) -> bool:
    """Bring a window to the foreground and give it focus.

    This is the recommended way to activate a window before performing
    actions. Replaces scattered SetForegroundWindow + ShowWindow calls.

    Args:
        window: pywinctl Window object (or title string).
        wait: If True, block until the window is actually active.

    Returns:
        True if activation succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)

    try:
        if window.isMinimized:
            window.restore(wait=wait)
        return bool(window.activate(wait=wait))
    except Exception as exc:
        logger.warning("Window activation failed: %s", exc)
        return False


def activate_by_hwnd(hwnd: int, wait: bool = True) -> bool:
    """Activate a window by its native handle.

    Args:
        hwnd: Native window handle.
        wait: If True, block until active.

    Returns:
        True if activation succeeded.
    """
    win = get_window_by_hwnd(hwnd)
    if win is None:
        logger.warning("No window found for hwnd=%s", hwnd)
        return False
    return activate(win, wait=wait)


def minimise(window: Any, wait: bool = True) -> bool:
    """Minimise a window.

    Args:
        window: pywinctl Window object (or title string).
        wait: If True, block until minimised.

    Returns:
        True if minimisation succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.minimize(wait=wait))
    except Exception as exc:
        logger.warning("Minimise failed: %s", exc)
        return False


def maximise(window: Any, wait: bool = True) -> bool:
    """Maximise a window.

    Args:
        window: pywinctl Window object (or title string).
        wait: If True, block until maximised.

    Returns:
        True if maximisation succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.maximize(wait=wait))
    except Exception as exc:
        logger.warning("Maximise failed: %s", exc)
        return False


def restore(window: Any, wait: bool = True) -> bool:
    """Restore a window from minimised/maximised state.

    Args:
        window: pywinctl Window object (or title string).
        wait: If True, block until restored.

    Returns:
        True if restoration succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.restore(wait=wait))
    except Exception as exc:
        logger.warning("Restore failed: %s", exc)
        return False


def move(window: Any, x: int, y: int, wait: bool = True) -> bool:
    """Move a window to absolute screen coordinates.

    Args:
        window: pywinctl Window object (or title string).
        x: Target left edge in pixels.
        y: Target top edge in pixels.
        wait: If True, block until moved.

    Returns:
        True if move succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.moveTo(x, y))
    except Exception as exc:
        logger.warning("Move failed: %s", exc)
        return False


def resize(window: Any, width: int, height: int, wait: bool = True) -> bool:
    """Resize a window to specific dimensions.

    Args:
        window: pywinctl Window object (or title string).
        width: Target width in pixels.
        height: Target height in pixels.
        wait: If True, block until resized.

    Returns:
        True if resize succeeded.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.resizeTo(width, height))
    except Exception as exc:
        logger.warning("Resize failed: %s", exc)
        return False


def get_geometry(window: Any) -> WindowGeometry:
    """Get the current position and size of a window.

    Args:
        window: pywinctl Window object (or title string).

    Returns:
        WindowGeometry with left, top, width, height.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        frame = window.getClientFrame()
        return WindowGeometry(
            left=int(frame.left),
            top=int(frame.top),
            width=int(frame.right - frame.left),
            height=int(frame.bottom - frame.top),
        )
    except Exception:
        # Fallback to box property if getClientFrame not available
        box = window.box if hasattr(window, "box") else None
        if box:
            return WindowGeometry(
                left=int(box.left), top=int(box.top),
                width=int(box.width), height=int(box.height),
            )
        raise


def is_alive(window: Any) -> bool:
    """Check if a window still exists."""
    try:
        return bool(window.isAlive())
    except Exception:
        return False


def is_active(window: Any) -> bool:
    """Check if a window is currently the foreground window."""
    try:
        return bool(window.isActive)
    except Exception:
        return False


def is_minimised(window: Any) -> bool:
    """Check if a window is minimised."""
    try:
        return bool(window.isMinimized)
    except Exception:
        return False


def is_maximised(window: Any) -> bool:
    """Check if a window is maximised."""
    try:
        return bool(window.isMaximized)
    except Exception:
        return False


def is_visible(window: Any) -> bool:
    """Check if a window is visible (not hidden)."""
    try:
        return bool(window.isVisible)
    except Exception:
        return False


def bring_to_front(window: Any) -> bool:
    """Raise a window above all others.

    Args:
        window: pywinctl Window object (or title string).

    Returns:
        True if the window was raised.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.raiseWindow())
    except Exception as exc:
        logger.warning("Raise failed: %s", exc)
        return False


def send_to_back(window: Any) -> bool:
    """Lower a window behind all others.

    Args:
        window: pywinctl Window object (or title string).

    Returns:
        True if the window was lowered.
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.lowerWindow())
    except Exception as exc:
        logger.warning("Lower failed: %s", exc)
        return False


def close(window: Any) -> bool:
    """Close a window.

    Args:
        window: pywinctl Window object (or title string).

    Returns:
        True if close was sent successfully. Note: the app may show
        a confirmation dialog (e.g., "Save changes?").
    """
    if isinstance(window, str):
        window = find_window(window)
    try:
        return bool(window.close())
    except Exception as exc:
        logger.warning("Close failed: %s", exc)
        return False


def get_display_info(window: Any) -> dict[str, Any]:
    """Get information about which monitor a window is on.

    Args:
        window: pywinctl Window object (or title string).

    Returns:
        Dict with monitor name, size, and work area.
    """
    if isinstance(window, str):
        window = find_window(window)
    pwc = _get_pywinctl()
    try:
        display = window.getDisplay()
        screen_size = pwc.getScreenSize(display)
        work_area = pwc.getWorkArea(display)
        return {
            "display": str(display),
            "screen_size": {"width": int(screen_size[0]), "height": int(screen_size[1])},
            "work_area": {
                "left": int(work_area[0]),
                "top": int(work_area[1]),
                "right": int(work_area[2]),
                "bottom": int(work_area[3]),
            },
        }
    except Exception as exc:
        logger.debug("Could not get display info: %s", exc)
        return {}


def get_all_screens() -> dict[str, Any]:
    """Get information about all connected monitors.

    Returns:
        Dict mapping monitor names to their properties.
    """
    pwc = _get_pywinctl()
    try:
        result: dict[str, Any] = dict(pwc.getAllScreens())
        return result
    except Exception as exc:
        logger.debug("Could not enumerate screens: %s", exc)
        return {}
