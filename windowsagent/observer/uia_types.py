"""
UI Automation type definitions and constants.

Dataclasses and string constants shared across the uia sub-modules.
External code should import UIAElement, UIATree, WindowInfo directly from
windowsagent.observer.uia (which re-exports everything here).
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
