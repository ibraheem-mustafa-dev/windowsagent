"""
UI Automation tree inspection module.

Uses pywinauto with the UIA backend to read the Windows accessibility tree.
This is the primary method for element targeting — faster, cheaper, and more
reliable than vision-based coordinate guessing.

Caching: UIA tree results are cached for config.uia_cache_ttl seconds to
avoid redundant IPC calls to target processes. Cache is keyed by (hwnd, max_depth).

Public API is re-exported here for backward compatibility:
    from windowsagent.observer.uia import UIAElement, UIATree, WindowInfo
    from windowsagent.observer.uia import get_windows, get_window, get_tree
    from windowsagent.observer.uia import find_element, is_webview2, invalidate_cache
"""

from __future__ import annotations

import logging
import time
from typing import Any

from windowsagent.exceptions import UIAError

# Re-export types — callers import from here, not from sub-modules
from windowsagent.observer.uia_types import (
    CONTROL_TYPES,
    PATTERN_NAMES,
    UIAElement,
    UIATree,
    WindowInfo,
)

# Re-export window helpers
from windowsagent.observer.uia_windows import get_window, get_windows

# Re-export search/build internals (find_element is public; _search_tree used in tests)
from windowsagent.observer.uia_internals import (
    _build_element,
    _count_elements,
    _search_tree,
    find_element,
)

logger = logging.getLogger(__name__)

# Module-level tree cache: maps (hwnd, max_depth) -> (UIATree, expire_time)
_tree_cache: dict[tuple[int, int], tuple[UIATree, float]] = {}

__all__ = [
    "CONTROL_TYPES",
    "PATTERN_NAMES",
    "UIAElement",
    "UIATree",
    "WindowInfo",
    "get_windows",
    "get_window",
    "get_tree",
    "find_element",
    "is_webview2",
    "invalidate_cache",
    "_search_tree",
]


def get_tree(
    window: Any,
    max_depth: int = 8,
    force_refresh: bool = False,
) -> UIATree:
    """Build the full UI Automation tree for a window.

    Results are cached for config.uia_cache_ttl seconds. Pass force_refresh=True
    to bypass the cache.

    Args:
        window: pywinauto.Application instance (from get_window()).
        max_depth: Maximum depth to traverse. Deeper = more complete but slower.
        force_refresh: Bypass cache if True.

    Returns:
        UIATree with full element hierarchy.

    Raises:
        UIAError: If tree inspection fails.
    """
    try:
        import pywinauto  # noqa: F401 — validates availability

        # Get the main window wrapper
        try:
            main_win = window.top_window()
        except Exception:
            main_win = window.active()

        hwnd = main_win.handle
        cache_key = (hwnd, max_depth)
        now = time.monotonic()

        # Check cache
        if not force_refresh and cache_key in _tree_cache:
            cached_tree, expire_time = _tree_cache[cache_key]
            if now < expire_time:
                logger.debug("UIA tree cache hit for HWND %d", hwnd)
                return cached_tree

        logger.debug("Building UIA tree for HWND %d (max_depth=%d)", hwnd, max_depth)

        title = main_win.window_text() or ""
        pid = 0
        app_name = "unknown.exe"
        try:
            pid = main_win.element_info.process_id
            import psutil
            app_name = psutil.Process(pid).name()
        except Exception:
            pass

        root_element = _build_element(main_win, depth=0, max_depth=max_depth)
        tree = UIATree(
            root=root_element,
            window_title=title,
            app_name=app_name,
            timestamp=time.time(),
            pid=pid,
            hwnd=hwnd,
        )

        # Cache the result
        from windowsagent.config import load_config
        ttl = load_config().uia_cache_ttl
        _tree_cache[cache_key] = (tree, now + ttl)

        logger.debug(
            "UIA tree built for %r: %d total elements",
            title,
            _count_elements(root_element),
        )
        return tree

    except UIAError:
        raise
    except ImportError as exc:
        raise UIAError("pywinauto not installed") from exc
    except Exception as exc:
        raise UIAError(f"get_tree failed: {exc}") from exc


def is_webview2(window: Any) -> bool:
    """Detect whether a window contains an Edge WebView2 control.

    WebView2 apps (Outlook, Teams, VS Code) require special handling because
    their inner content is not fully exposed via the UIA tree.

    Args:
        window: pywinauto.Application instance.

    Returns:
        True if the window contains a WebView2 host element.
    """
    webview2_class_names = (
        "Chrome_WidgetWin_1",
        "Chrome_RenderWidgetHostHWND",
        "WebView2",
        "CefBrowserWindow",
    )

    try:
        main_win = window.top_window()
    except Exception:
        try:
            main_win = window.active()
        except Exception:
            return False

    def _check_class(element: UIAElement) -> bool:
        if element.class_name in webview2_class_names:
            return True
        return any(_check_class(child) for child in element.children)

    try:
        tree = get_tree(main_win if hasattr(main_win, "rectangle") else window, max_depth=4)
        return _check_class(tree.root)
    except Exception:
        # Try checking child windows directly via Win32
        try:
            import ctypes
            hwnd = main_win.handle

            found = [False]

            def enum_child(child_hwnd: int, _: int) -> bool:
                class_buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetClassNameW(child_hwnd, class_buf, 256)
                if class_buf.value in webview2_class_names:
                    found[0] = True
                    return False  # Stop enumeration
                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumChildWindows(hwnd, EnumWindowsProc(enum_child), 0)
            return found[0]
        except Exception:
            return False


def invalidate_cache(hwnd: int | None = None) -> None:
    """Invalidate cached UIA trees.

    Args:
        hwnd: If provided, only invalidate entries for this window.
              If None, clear the entire cache.
    """
    global _tree_cache
    if hwnd is None:
        _tree_cache.clear()
        logger.debug("UIA tree cache cleared entirely")
    else:
        keys_to_remove = [k for k in _tree_cache if k[0] == hwnd]
        for k in keys_to_remove:
            del _tree_cache[k]
        logger.debug("UIA tree cache cleared for HWND %d", hwnd)
