"""
UI Automation tree inspection module.

Uses pywinauto with the UIA backend to read the Windows accessibility tree.
This is the primary method for element targeting — faster, cheaper, and more
reliable than vision-based coordinate guessing.

Caching: UIA tree results are cached for config.uia_cache_ttl seconds to
avoid redundant IPC calls to target processes. Cache is keyed by (hwnd, max_depth).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import UIAError, WindowNotFoundError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Control type string constants (subset most commonly used)
CONTROL_TYPES = frozenset(
    [
        "Button",
        "Calendar",
        "CheckBox",
        "ComboBox",
        "Custom",
        "DataGrid",
        "DataItem",
        "Document",
        "Edit",
        "Group",
        "Header",
        "HeaderItem",
        "Hyperlink",
        "Image",
        "List",
        "ListItem",
        "Menu",
        "MenuBar",
        "MenuItem",
        "Pane",
        "ProgressBar",
        "RadioButton",
        "ScrollBar",
        "Separator",
        "Slider",
        "Spinner",
        "SplitButton",
        "StatusBar",
        "Tab",
        "TabItem",
        "Table",
        "Text",
        "ThumbRule",
        "TitleBar",
        "ToolBar",
        "ToolTip",
        "Tree",
        "TreeItem",
        "Window",
    ]
)

# Pattern names that indicate interaction capabilities
PATTERN_NAMES = {
    "InvokePattern": "invoke",
    "ValuePattern": "value",
    "SelectionPattern": "selection",
    "SelectionItemPattern": "selection_item",
    "ScrollPattern": "scroll",
    "ScrollItemPattern": "scroll_item",
    "ExpandCollapsePattern": "expand_collapse",
    "TogglePattern": "toggle",
    "TextPattern": "text",
    "GridPattern": "grid",
    "GridItemPattern": "grid_item",
    "TablePattern": "table",
    "TableItemPattern": "table_item",
    "RangeValuePattern": "range_value",
    "WindowPattern": "window",
    "TransformPattern": "transform",
    "LegacyIAccessiblePattern": "legacy_iaccessible",
}

# Module-level tree cache: maps (hwnd, max_depth) -> (UIATree, expire_time)
_tree_cache: dict[tuple[int, int], tuple[UIATree, float]] = {}


@dataclass
class UIAElement:
    """Represents a single element in the Windows UI Automation tree.

    All rect coordinates are in logical pixels (screen coordinates).
    """

    name: str                              # Accessible name (e.g. "Send", "File")
    control_type: str                      # "Button", "Edit", "List", etc.
    automation_id: str                     # Developer-assigned ID (most stable identifier)
    class_name: str                        # Win32 class name
    rect: tuple[int, int, int, int]       # (left, top, right, bottom) logical pixels
    is_enabled: bool
    is_visible: bool                       # False if off-screen or hidden
    patterns: list[str]                    # Available UIA patterns (e.g. ["invoke", "value"])
    value: str                             # Current value/text (from ValuePattern or LegacyIA)
    children: list[UIAElement] = field(default_factory=list)
    depth: int = 0                         # Depth in tree (root = 0)
    hwnd: int = 0                          # Native window handle (0 if not directly accessible)

    @property
    def centre(self) -> tuple[int, int]:
        """Return the centre point of this element's bounding rect."""
        left, t, r, b = self.rect
        return ((left + r) // 2, (t + b) // 2)

    @property
    def is_interactable(self) -> bool:
        """Return True if this element has at least one interaction pattern."""
        return bool(self.patterns) and self.is_enabled and self.is_visible


@dataclass
class UIATree:
    """The full UI Automation tree for a window."""

    root: UIAElement
    window_title: str
    app_name: str              # Process name (e.g. "notepad.exe")
    timestamp: float
    pid: int
    hwnd: int


@dataclass
class WindowInfo:
    """Summary information about a top-level window."""

    title: str
    app_name: str
    pid: int
    hwnd: int
    rect: tuple[int, int, int, int]
    is_visible: bool
    is_enabled: bool


def get_windows() -> list[WindowInfo]:
    """Return a list of all visible, non-minimised top-level windows.

    Returns:
        List of WindowInfo for each qualifying window.
    """
    try:
        import pywinauto

        desktop = pywinauto.Desktop(backend="uia")
        windows: list[WindowInfo] = []

        for win in desktop.windows():
            try:
                if not win.is_visible():
                    continue
                title = win.window_text() or ""
                if not title.strip():
                    continue

                rect = win.rectangle()
                proc_name = ""
                pid = 0
                try:
                    proc_name = win.element_info.process_id
                    pid = int(proc_name)
                    import psutil
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                except Exception:
                    proc_name = "unknown.exe"

                windows.append(
                    WindowInfo(
                        title=title,
                        app_name=proc_name,
                        pid=pid,
                        hwnd=win.handle,
                        rect=(rect.left, rect.top, rect.right, rect.bottom),
                        is_visible=win.is_visible(),
                        is_enabled=win.is_enabled(),
                    )
                )
            except Exception as exc:
                logger.debug("Skipping window during enumeration: %s", exc)

        return windows

    except ImportError as exc:
        raise UIAError("pywinauto not installed") from exc
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


def find_element(
    tree: UIATree,
    name: str | None = None,
    control_type: str | None = None,
    automation_id: str | None = None,
    value: str | None = None,
) -> UIAElement | None:
    """Find the best matching element in a UIA tree.

    Matching algorithm (stops at first match, in order of precision):
    1. Exact automation_id match
    2. Exact name + exact control_type match
    3. Case-insensitive name + control_type match
    4. Partial name match (search term contained in element name)
    5. Value match (search term contained in element.value)

    Args:
        tree: The UIATree to search.
        name: Element name to search for.
        control_type: Element control type (e.g. "Button", "Edit").
        automation_id: Automation ID string.
        value: Value/text to match.

    Returns:
        Best matching UIAElement, or None if not found.
    """
    if not any([name, control_type, automation_id, value]):
        return None

    # Normalise search terms
    name_lower: str = name.lower() if name else ""
    type_lower: str = control_type.lower() if control_type else ""

    # Pass 1: exact automation_id
    if automation_id:
        result = _search_tree(
            tree.root,
            lambda e: e.automation_id == automation_id,
        )
        if result:
            return result

    # Pass 2: exact name + exact type
    if name and control_type:
        result = _search_tree(
            tree.root,
            lambda e: (
                e.name == name
                and e.control_type.lower() == type_lower
            ),
        )
        if result:
            return result

    # Pass 3: case-insensitive name + type
    if name and control_type:
        result = _search_tree(
            tree.root,
            lambda e: (
                e.name.lower() == name_lower
                and e.control_type.lower() == type_lower
            ),
        )
        if result:
            return result

    # Pass 4: exact name only (case-insensitive)
    if name:
        result = _search_tree(
            tree.root,
            lambda e: e.name.lower() == name_lower,
        )
        if result:
            return result

    # Pass 5: partial name match
    if name:
        result = _search_tree(
            tree.root,
            lambda e: name_lower in e.name.lower(),
        )
        if result:
            return result

    # Pass 6: control_type only
    if control_type and not name:
        result = _search_tree(
            tree.root,
            lambda e: e.control_type.lower() == type_lower,
        )
        if result:
            return result

    # Pass 7: value match
    if value:
        value_lower = value.lower()
        result = _search_tree(
            tree.root,
            lambda e: value_lower in e.value.lower(),
        )
        if result:
            return result

    return None


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


# ── Private helpers ──────────────────────────────────────────────────────────


def _build_element(wrapper: Any, depth: int, max_depth: int) -> UIAElement:
    """Recursively build a UIAElement from a pywinauto wrapper."""
    try:
        name = wrapper.window_text() or ""
    except Exception:
        name = ""

    try:
        ctrl_type = wrapper.element_info.control_type or "Unknown"
        # pywinauto returns integer or string; normalise to string
        if not isinstance(ctrl_type, str):
            ctrl_type = str(ctrl_type)
    except Exception:
        ctrl_type = "Unknown"

    try:
        automation_id = wrapper.element_info.automation_id or ""
    except Exception:
        automation_id = ""

    try:
        class_name = wrapper.element_info.class_name or ""
    except Exception:
        class_name = ""

    try:
        rect_obj = wrapper.rectangle()
        rect = (rect_obj.left, rect_obj.top, rect_obj.right, rect_obj.bottom)
    except Exception:
        rect = (0, 0, 0, 0)

    try:
        is_enabled = wrapper.is_enabled()
    except Exception:
        is_enabled = False

    try:
        is_visible = wrapper.is_visible()
    except Exception:
        is_visible = False

    try:
        hwnd = wrapper.handle
    except Exception:
        hwnd = 0

    # Detect available patterns
    patterns: list[str] = []
    try:
        for pattern_name, short_name in PATTERN_NAMES.items():
            try:
                if hasattr(wrapper, pattern_name.lower().replace("pattern", "")):
                    patterns.append(short_name)
            except Exception:
                pass
        # Also check via element_info patterns if available
        if hasattr(wrapper, "element_info") and hasattr(wrapper.element_info, "patterns"):
            for p in wrapper.element_info.patterns:
                p_short = PATTERN_NAMES.get(p, p.lower().replace("pattern", ""))
                if p_short not in patterns:
                    patterns.append(p_short)
    except Exception:
        pass

    # Read current value
    value = ""
    try:
        value = wrapper.legacy_properties().get("Value", "") or ""
    except Exception:
        pass
    if not value:
        try:
            value = wrapper.get_value() or ""
        except Exception:
            pass

    # Build children
    children: list[UIAElement] = []
    if depth < max_depth:
        try:
            for child in wrapper.children():
                try:
                    child_elem = _build_element(child, depth + 1, max_depth)
                    children.append(child_elem)
                except Exception as exc:
                    logger.debug("Skipping child element at depth %d: %s", depth + 1, exc)
        except Exception as exc:
            logger.debug("Could not get children at depth %d: %s", depth, exc)

    return UIAElement(
        name=name,
        control_type=ctrl_type,
        automation_id=automation_id,
        class_name=class_name,
        rect=rect,
        is_enabled=is_enabled,
        is_visible=is_visible,
        patterns=patterns,
        value=value,
        children=children,
        depth=depth,
        hwnd=hwnd,
    )


def _search_tree(
    element: UIAElement,
    predicate: Callable[[UIAElement], bool],
) -> UIAElement | None:
    """Depth-first search of the UIA tree using a predicate function."""
    try:
        if predicate(element):
            return element
    except Exception:
        pass

    for child in element.children:
        result = _search_tree(child, predicate)
        if result:
            return result

    return None


def _count_elements(element: UIAElement) -> int:
    """Count total elements in a UIAElement subtree."""
    return 1 + sum(_count_elements(c) for c in element.children)
