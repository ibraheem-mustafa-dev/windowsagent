"""
WebView2 handler — special handling for Edge WebView2 applications.

WebView2 apps (new Outlook, Teams, VS Code, many Electron apps) embed a
Chromium-based renderer inside a Win32 host window. This creates specific
automation challenges:

1. Mouse wheel scroll does NOT reliably reach inner WebView2 content
2. Virtualised lists only expose ~15 items in the UIA tree at once
3. The inner accessibility tree is shallower than native apps
4. Focus can shift between the Win32 host and the WebView content unexpectedly

Strategy:
- Scroll by clicking in content area + sending keyboard Page Down/Up keys
- Find virtualised items by scroll + re-inspect loop
- Detect WebView2 by checking for Chrome_WidgetWin_1 child windows
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import UIAElement, UIATree, WindowInfo

logger = logging.getLogger(__name__)

# Win32 class names that indicate a WebView2 host window
WEBVIEW2_CLASS_NAMES: frozenset[str] = frozenset(
    [
        "Chrome_WidgetWin_1",
        "Chrome_RenderWidgetHostHWND",
        "WebView2",
        "CefBrowserWindow",
    ]
)

# Process names that are always WebView2-based
WEBVIEW2_PROCESS_NAMES: frozenset[str] = frozenset(
    [
        "msedgewebview2.exe",
        "electronapp.exe",
    ]
)


def is_webview2_process(process_name: str) -> bool:
    """Return True if the process is known to be WebView2-based."""
    return process_name.lower() in WEBVIEW2_PROCESS_NAMES


def is_webview2(window: Any) -> bool:
    """Detect whether a window contains an Edge WebView2 control.

    Checks child window class names for known WebView2 identifiers.

    Args:
        window: pywinauto.Application instance.

    Returns:
        True if a WebView2 host element is found in the window.
    """
    try:
        main_win = window.top_window()
    except Exception:
        try:
            main_win = window.active()
        except Exception:
            return False

    try:
        import ctypes

        hwnd = main_win.handle
        found: list[bool] = [False]

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _enum_child(child_hwnd: int, _: int) -> bool:
            class_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(child_hwnd, class_buf, 256)
            if class_buf.value in WEBVIEW2_CLASS_NAMES:
                found[0] = True
                return False  # Stop enumeration
            return True  # Continue

        ctypes.windll.user32.EnumChildWindows(hwnd, EnumWindowsProc(_enum_child), 0)
        return found[0]
    except Exception as exc:
        logger.debug("WebView2 detection failed: %s", exc)
        return False


def scroll_content(
    window: Any,
    direction: str,
    amount: int,
    config: Config,
) -> bool:
    """Scroll WebView2 content by clicking in it and sending keyboard events.

    Mouse wheel scroll does not reliably reach the inner WebView2 renderer.
    Instead: click inside the content area to establish keyboard focus, then
    send Page Down/Up keys which DO reach the WebView2 content.

    Args:
        window: pywinauto.Application for the target window.
        direction: "up" or "down".
        amount: Number of page scrolls.
        config: WindowsAgent configuration.

    Returns:
        True if scroll detected (screenshot diff > 2%), False otherwise.
    """
    try:
        main_win = window.top_window()
        hwnd = main_win.handle
        rect_obj = main_win.rectangle()
        content_x = (rect_obj.left + rect_obj.right) // 2
        content_y = (rect_obj.top + rect_obj.bottom) // 2
    except Exception as exc:
        logger.warning("Could not get window rect for scroll: %s", exc)
        return False

    try:
        from windowsagent.actor.input_actor import click_at, press_key
        from windowsagent.observer.screenshot import capture_window
        from windowsagent.verifier.verify import screenshot_diff

        screenshot_before = capture_window(hwnd, config)

        # Click inside content to ensure keyboard focus
        click_at(content_x, content_y, config=config)
        time.sleep(0.1)

        # Send keyboard scroll
        key = "page_down" if direction == "down" else "page_up"
        for _ in range(amount):
            press_key(key, config=config)
            time.sleep(0.05)

        # Wait for render
        time.sleep(0.3)

        screenshot_after = capture_window(hwnd, config)
        diff = screenshot_diff(screenshot_before, screenshot_after)

        if diff > 0.02:
            logger.debug(
                "WebView2 scroll %s x%d succeeded (diff=%.1f%%)", direction, amount, diff * 100
            )
            return True
        else:
            logger.debug(
                "WebView2 scroll %s x%d produced no change (diff=%.1f%%)",
                direction,
                amount,
                diff * 100,
            )
            return False

    except Exception as exc:
        logger.warning("WebView2 scroll failed: %s", exc)
        return False


def find_virtualised_item(
    window: Any,
    target_text: str,
    config: Config,
    max_scrolls: int = 20,
) -> UIAElement | None:
    """Find a virtualised list item by scrolling and re-inspecting the UIA tree.

    WebView2 virtualised lists only expose currently visible items in the UIA
    tree. This function scrolls down page by page, re-inspecting after each
    scroll, until the target is found or the bottom is reached.

    Args:
        window: pywinauto.Application for the target window.
        target_text: Text to search for in element names/values.
        config: WindowsAgent configuration.
        max_scrolls: Maximum number of page scrolls before giving up.

    Returns:
        UIAElement if found, None if not found after max_scrolls pages.
    """
    from windowsagent.observer.uia import find_element, get_tree, invalidate_cache

    target_lower = target_text.lower()

    for scroll_attempt in range(max_scrolls + 1):
        # Refresh the UIA tree
        try:
            main_win = window.top_window()
            invalidate_cache(main_win.handle)
        except Exception:
            pass

        try:
            tree = get_tree(window, max_depth=6, force_refresh=True)
        except Exception as exc:
            logger.warning("Could not get tree during virtualised item search: %s", exc)
            break

        # Search current visible items
        result = find_element(tree, name=target_text)
        if result is None:
            # Try partial match
            from windowsagent.observer.uia import _search_tree
            result = _search_tree(
                tree.root,
                lambda e: target_lower in e.name.lower() or target_lower in e.value.lower(),
            )

        if result is not None:
            logger.debug(
                "Found virtualised item %r after %d scrolls", target_text, scroll_attempt
            )
            return result

        if scroll_attempt < max_scrolls:
            # Scroll down one page and try again
            scrolled = scroll_content(window, "down", 1, config)
            if not scrolled:
                logger.debug("WebView2 scroll returned no change — probably at bottom of list")
                break

    logger.debug("Virtualised item %r not found after %d scrolls", target_text, max_scrolls)
    return None


def get_inner_tree(window: Any, config: Config) -> UIATree:
    """Extract the inner UIA tree from a WebView2 host.

    For WebView2 apps, the useful content is nested inside the WebView2 host
    element. This function finds that host and returns a tree rooted at it.

    Args:
        window: pywinauto.Application for the WebView2 host window.
        config: WindowsAgent configuration.

    Returns:
        UIATree rooted at the WebView2 content element.
    """
    from windowsagent.observer.uia import get_tree

    # The WebView2 inner content is accessible via the same get_tree() call,
    # but we can try to go deeper since the host adds shallow wrapper layers
    return get_tree(window, max_depth=10, force_refresh=True)


class WebView2Profile(BaseAppProfile):
    """App profile for any WebView2-based application.

    Used as a fallback for apps detected as WebView2 but without a
    dedicated profile (e.g. Electron apps, custom WebView2 tools).
    """

    app_names: ClassVar[list[str]] = list(WEBVIEW2_PROCESS_NAMES)
    window_titles: ClassVar[list[str]] = []

    def is_match(self, window_info: WindowInfo) -> bool:
        return is_webview2_process(window_info.app_name)

    def get_scroll_strategy(self) -> str:  # type: ignore[override]
        return "webview2"

    def requires_focus_restore(self) -> bool:
        return True
