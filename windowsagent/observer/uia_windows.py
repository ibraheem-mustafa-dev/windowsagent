"""
Window enumeration and connection helpers for UI Automation.

Provides get_windows() and get_window() — the entry points for finding
and connecting to target Windows processes. External code should import
these from windowsagent.observer.uia.
"""

from __future__ import annotations

import logging
from typing import Any

from windowsagent.exceptions import UIAError, WindowNotFoundError
from windowsagent.observer.uia_types import WindowInfo

logger = logging.getLogger(__name__)


def get_windows() -> list[WindowInfo]:
    """Return a list of all visible, non-minimised top-level windows.

    Uses win32gui.EnumWindows for reliable enumeration (pywinauto UIA backend
    can return is_visible()=False for all windows when called from a non-interactive
    process context). pywinauto is still used for tree inspection once we have an hwnd.

    Returns:
        List of WindowInfo for each qualifying window.
    """
    try:
        import psutil
        import win32con
        import win32gui

        raw_hwnds: list[int] = []

        def _enum_cb(hwnd: int, _: object) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.IsIconic(hwnd):  # minimised
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title.strip():
                return True
            # Skip windows with WS_EX_TOOLWINDOW (system tray popups, etc.)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                return True
            raw_hwnds.append(hwnd)
            return True

        win32gui.EnumWindows(_enum_cb, None)

        windows: list[WindowInfo] = []
        for hwnd in raw_hwnds:
            try:
                title = win32gui.GetWindowText(hwnd)
                rect_tuple = win32gui.GetWindowRect(hwnd)
                left, top, right, bottom = rect_tuple

                pid = 0
                proc_name = "unknown.exe"
                try:
                    import win32process
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                except Exception:
                    pass

                windows.append(
                    WindowInfo(
                        title=title,
                        app_name=proc_name,
                        pid=pid,
                        hwnd=hwnd,
                        rect=(left, top, right, bottom),
                        is_visible=True,
                        is_enabled=bool(win32gui.IsWindowEnabled(hwnd)),
                    )
                )
            except Exception as exc:
                logger.debug("Skipping window hwnd=%s during enumeration: %s", hwnd, exc)

        return windows

    except ImportError as exc:
        raise UIAError("win32gui/psutil not installed — install pywin32 and psutil") from exc
    except Exception as exc:
        raise UIAError(f"get_windows failed: {exc}") from exc


def get_window(
    title: str | None = None,
    pid: int | None = None,
    hwnd: int | None = None,
) -> Any:
    """Find and return a pywinauto Application connected to the target window.

    Provide at least one of title, pid, or hwnd. If multiple criteria are
    given, all must match.

    Args:
        title: Partial window title (case-insensitive substring match).
        pid: Process ID.
        hwnd: Native window handle.

    Returns:
        Connected pywinauto.Application instance.

    Raises:
        WindowNotFoundError: If no matching window is found.
        UIAError: If pywinauto is not installed or crashes.
    """
    if title is None and pid is None and hwnd is None:
        raise UIAError("get_window requires at least one of: title, pid, hwnd")

    try:
        import pywinauto

        app = pywinauto.Application(backend="uia")

        if hwnd is not None:
            try:
                app.connect(handle=hwnd)
                return app
            except pywinauto.application.ProcessNotFoundError as exc:
                raise WindowNotFoundError(f"hwnd={hwnd}") from exc

        if pid is not None:
            try:
                app.connect(process=pid)
                return app
            except pywinauto.application.ProcessNotFoundError as exc:
                raise WindowNotFoundError(f"pid={pid}") from exc

        # Search by title substring
        assert title is not None
        title_lower = title.lower()
        for win_info in get_windows():
            if title_lower in win_info.title.lower():
                try:
                    app.connect(handle=win_info.hwnd)
                    return app
                except Exception as exc:
                    logger.debug("Could not connect to window %r: %s", win_info.title, exc)

        raise WindowNotFoundError(title)

    except WindowNotFoundError:
        raise
    except ImportError as exc:
        raise UIAError("pywinauto not installed") from exc
    except Exception as exc:
        raise UIAError(f"get_window failed: {exc}") from exc
