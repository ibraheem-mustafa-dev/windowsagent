"""
AppState — combined snapshot of a window's current state.

Combines UIA tree + screenshot + OCR results into a single object that the
agent loop, grounder, and verifier all work from.

The capture() function runs screenshot and UIA tree capture concurrently
(using ThreadPoolExecutor) to minimise total capture time.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import ObserverError
from windowsagent.observer.screenshot import Screenshot, capture_window
from windowsagent.observer.uia import UIAElement, UIATree, get_tree, get_window, is_webview2

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.ocr import OCRResult

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Complete state snapshot of a Windows application at a moment in time.

    All fields that could not be captured are set to None or empty defaults —
    capture() never raises if a single component fails; it logs a warning and
    returns a partial state instead.
    """

    uia_tree: UIATree
    screenshot: Screenshot
    ocr_results: list[OCRResult] = field(default_factory=list)
    focused_element: UIAElement | None = None
    window_title: str = ""
    app_name: str = ""
    pid: int = 0
    hwnd: int = 0
    timestamp: float = field(default_factory=time.time)
    is_webview2_app: bool = False


@dataclass
class StateDiff:
    """The difference between two AppState snapshots.

    Useful for verifying that an action produced the expected change.
    """

    new_elements: list[UIAElement]      # Elements in 'after' but not in 'before'
    removed_elements: list[UIAElement]  # Elements in 'before' but not in 'after'
    changed_elements: list[UIAElement]  # Elements whose name/value changed
    screenshot_diff_pct: float          # Fraction of pixels changed (0.0-1.0)
    has_new_window: bool                # A new top-level window appeared
    has_dialog: bool                    # A dialog/modal appeared in the UIA tree


def capture(window_title: str, config: Config) -> AppState:
    """Capture the complete current state of a window.

    Runs screenshot and UIA tree capture concurrently for speed. OCR is run
    after the screenshot if enabled. If any individual component fails, a
    warning is logged and a partial state is returned.

    Args:
        window_title: Window title to capture (partial match supported).
        config: WindowsAgent configuration.

    Returns:
        AppState with all available information populated.

    Raises:
        WindowNotFoundError: If the target window cannot be found.
        ObserverError: If both screenshot and UIA capture fail completely.
    """
    timestamp = time.time()

    # Find the window first (raises WindowNotFoundError if not found)
    window = get_window(title=window_title)

    # Get HWND for screenshot capture
    hwnd = 0
    try:
        main_win = window.top_window()
        hwnd = main_win.handle
    except Exception:
        try:
            hwnd = window.active().handle
        except Exception:
            logger.warning("Could not get HWND for %r, using full-screen capture", window_title)

    uia_tree: UIATree | None = None
    screenshot: Screenshot | None = None

    # Run UIA and screenshot capture concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        uia_future = executor.submit(_safe_get_tree, window, config)
        screenshot_future = executor.submit(_safe_capture_window, hwnd, config)

        for future in as_completed([uia_future, screenshot_future]):  # type: ignore[arg-type, var-annotated]
            result = future.result()
            if isinstance(result, UIATree):
                uia_tree = result
            elif isinstance(result, Screenshot):
                screenshot = result

    if uia_tree is None and screenshot is None:
        raise ObserverError(
            f"Both UIA tree and screenshot capture failed for {window_title!r}",
            retryable=True,
        )

    # If one component failed, create a minimal placeholder
    if uia_tree is None:
        logger.warning("UIA tree capture failed for %r, state will be partial", window_title)
        from windowsagent.observer.uia import UIAElement as _UIAEl
        placeholder_element = _UIAEl(
            name=window_title,
            control_type="Window",
            automation_id="",
            class_name="",
            rect=(0, 0, 0, 0),
            is_enabled=True,
            is_visible=True,
            patterns=[],
            value="",
        )
        from windowsagent.observer.uia import UIATree as _UIATree
        uia_tree = _UIATree(
            root=placeholder_element,
            window_title=window_title,
            app_name="unknown.exe",
            timestamp=timestamp,
            pid=0,
            hwnd=hwnd,
        )

    if screenshot is None:
        logger.warning("Screenshot capture failed for %r, proceeding without screenshot", window_title)
        # This is a hard failure for any vision-based operation but the agent loop
        # can still do UIA-only actions
        raise ObserverError(
            f"Screenshot capture failed for {window_title!r}", retryable=True
        )

    # OCR (runs after screenshot, synchronously)
    ocr_results: list[OCRResult] = []
    if config.ocr_backend != "none" and screenshot is not None:
        try:
            from windowsagent.observer.ocr import extract_text
            ocr_results = extract_text(screenshot, config)
            logger.debug("OCR extracted %d text regions", len(ocr_results))
        except Exception as exc:
            logger.warning("OCR extraction failed: %s", exc)

    # Detect focused element
    focused_element: UIAElement | None = None
    try:
        focused_element = _find_focused_element(window, uia_tree)
    except Exception as exc:
        logger.debug("Could not determine focused element: %s", exc)

    # Detect WebView2
    webview2 = False
    try:
        webview2 = is_webview2(window)
    except Exception:
        pass

    return AppState(
        uia_tree=uia_tree,
        screenshot=screenshot,
        ocr_results=ocr_results,
        focused_element=focused_element,
        window_title=uia_tree.window_title or window_title,
        app_name=uia_tree.app_name,
        pid=uia_tree.pid,
        hwnd=uia_tree.hwnd or hwnd,
        timestamp=timestamp,
        is_webview2_app=webview2,
    )


def diff(before: AppState, after: AppState) -> StateDiff:
    """Compute the difference between two AppState snapshots.

    Args:
        before: State captured before an action.
        after: State captured after an action.

    Returns:
        StateDiff describing what changed.
    """
    from windowsagent.verifier.verify import screenshot_diff as _screenshot_diff

    # Compute pixel diff
    pixel_diff = 0.0
    try:
        pixel_diff = _screenshot_diff(before.screenshot, after.screenshot)
    except Exception as exc:
        logger.warning("Screenshot diff failed: %s", exc)

    # Build element identity sets
    before_map = _build_element_map(before.uia_tree.root)
    after_map = _build_element_map(after.uia_tree.root)

    before_keys = set(before_map.keys())
    after_keys = set(after_map.keys())

    new_keys = after_keys - before_keys
    removed_keys = before_keys - after_keys
    common_keys = before_keys & after_keys

    new_elements = [after_map[k] for k in new_keys]
    removed_elements = [before_map[k] for k in removed_keys]

    # Changed: same key but different value
    changed_elements = [
        after_map[k]
        for k in common_keys
        if after_map[k].value != before_map[k].value
        or after_map[k].name != before_map[k].name
    ]

    # Check for new windows (dialog detection)
    has_new_window = any(e.control_type == "Window" for e in new_elements)
    has_dialog = any(
        e.control_type in ("Window", "Pane") and "dialog" in e.name.lower()
        for e in new_elements
    )

    return StateDiff(
        new_elements=new_elements,
        removed_elements=removed_elements,
        changed_elements=changed_elements,
        screenshot_diff_pct=pixel_diff,
        has_new_window=has_new_window,
        has_dialog=has_dialog,
    )


# ── Private helpers ──────────────────────────────────────────────────────────


def _safe_get_tree(window: Any, config: Config) -> UIATree | None:
    """Get UIA tree, returning None on failure instead of raising."""
    try:
        return get_tree(window)
    except Exception as exc:
        logger.warning("UIA tree capture failed: %s", exc)
        return None


def _safe_capture_window(hwnd: int, config: Config) -> Screenshot | None:
    """Capture screenshot, returning None on failure instead of raising."""
    try:
        if hwnd:
            return capture_window(hwnd, config)
        from windowsagent.observer.screenshot import capture_full
        return capture_full(config)
    except Exception as exc:
        logger.warning("Screenshot capture failed: %s", exc)
        return None


def _find_focused_element(window: Any, tree: UIATree) -> UIAElement | None:
    """Find the currently focused element in the UIA tree."""
    try:
        import pywinauto
        focused = pywinauto.Desktop(backend="uia").get_focus()
        if focused is None:
            return None
        focused_name = focused.window_text() or ""
        focused_type = str(focused.element_info.control_type or "")
        focused_id = focused.element_info.automation_id or ""

        from windowsagent.observer.uia import find_element
        return find_element(
            tree,
            name=focused_name if focused_name else None,
            control_type=focused_type if focused_type else None,
            automation_id=focused_id if focused_id else None,
        )
    except Exception:
        return None


def _build_element_map(root: UIAElement) -> dict[str, UIAElement]:
    """Build a flat dict mapping element identity string → UIAElement.

    Identity is (automation_id or name) + control_type + depth to handle
    duplicate names at different positions.
    """
    result: dict[str, UIAElement] = {}

    def _visit(element: UIAElement) -> None:
        # Build a stable key
        key_parts = [
            element.automation_id or element.name or "",
            element.control_type,
            str(element.depth),
        ]
        key = "|".join(key_parts)
        # Handle duplicates by appending an index
        if key in result:
            i = 2
            while f"{key}#{i}" in result:
                i += 1
            key = f"{key}#{i}"
        result[key] = element
        for child in element.children:
            _visit(child)

    _visit(root)
    return result
