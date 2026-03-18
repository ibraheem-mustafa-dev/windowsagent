"""
Microsoft Excel app profile.

Excel is a Win32/COM application with strong UIA support. Key UIA elements:
- Name Box (ComboBox, AutomationId="13"): cell address navigator
- Ribbon buttons: standard toolbar buttons with known UIA names
- Sheet tabs and Formula Bar are NOT exposed as named UIA elements

Verified against live Excel (Microsoft 365, Windows 11 UK English) on 2026-03-18.

Locale note: Button names depend on Windows display language. This profile uses
UK English names (e.g. "Font Colour", "Centre"). US English systems will show
"Font Color", "Center" etc. The grounder's substring matching in get_element_hint()
handles minor variations, but locale-specific names are provided as alternatives.

Automation notes:
- Text input via clipboard is more reliable than type_keys for cell addresses
  (e.g. "A1:C10" contains a colon that can confuse keystroke simulation)
- Excel is Win32/COM — no WebView2 complexity, scroll_pattern works natively
- Excel does NOT steal focus after actions (unlike Outlook/Teams)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo

logger = logging.getLogger(__name__)


class ExcelProfile(BaseAppProfile):
    """App profile for Microsoft Excel (excel.exe).

    Covers Excel for Windows (Microsoft 365 and perpetual editions).
    Sheet tabs, Name Box navigation, and formula bar reading are supported
    via well-known UIA AutomationIds.
    """

    app_names: ClassVar[list[str]] = ["excel.exe"]
    window_titles: ClassVar[list[str]] = ["Excel", "Microsoft Excel"]

    known_elements: ClassVar[dict[str, str]] = {
        # Cell navigation — ComboBox aid="13", Edit aid="1001"
        "name box":             "Name Box",
        "cell address":         "Name Box",
        "cell reference":       "Name Box",
        "go to cell":           "Name Box",

        # NOTE: Formula Bar and Sheet tabs are NOT exposed as named UIA elements
        # in Excel (Microsoft 365). Use keyboard shortcuts instead:
        #   Formula Bar: F2 to edit, Escape to cancel
        #   Sheet tabs:  Ctrl+PageDown / Ctrl+PageUp to navigate

        # Home tab — Clipboard group
        "paste":                "Paste",
        "copy":                 "Copy",
        "cut":                  "Cut",
        "format painter":       "Format Painter",

        # Home tab — Font group
        "bold":                 "Bold",
        "italic":               "Italic",
        "underline":            "Underline",
        "font size":            "Font Size",
        "font colour":          "Font Colour",
        "font color":           "Font Colour",       # US English alias

        # Home tab — Alignment group
        "merge cells":          "Merge & Centre",
        "merge and centre":     "Merge & Centre",
        "merge and center":     "Merge & Centre",    # US English alias
        "wrap text":            "Wrap Text",
        "align left":           "Align Left",
        "align right":          "Align Right",
        "centre":               "Centre",
        "center":               "Centre",            # US English alias

        # Home tab — Number group
        "currency format":      "Accounting Number Format",
        "accounting":           "Accounting Number Format",
        "percent":              "Percent Style",
        "comma style":          "Comma Style",
        "number format":        "Number Format",

        # Home tab — Editing group
        "autosum":              "AutoSum",
        "sum":                  "AutoSum",
        "sort and filter":      "Sort & Filter",
        "sort":                 "Sort & Filter",
        "find and replace":     "Find & Select",
        "find":                 "Find & Select",
        "find and select":      "Find & Select",

        # Insert tab
        "insert table":         "Table",
        "table":                "Table",
        "insert pivot table":   "PivotTable",
        "pivot table":          "PivotTable",

        # Quick Access Toolbar
        "save":                 "Save",
        "undo":                 "Undo",
        "redo":                 "Redo",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        # File
        "save":                 "ctrl,s",
        "save_as":              "ctrl,shift,s",
        "new_workbook":         "ctrl,n",
        "open":                 "ctrl,o",
        "print":                "ctrl,p",
        "close":                "ctrl,w",

        # Edit
        "undo":                 "ctrl,z",
        "redo":                 "ctrl,y",
        "copy":                 "ctrl,c",
        "cut":                  "ctrl,x",
        "paste":                "ctrl,v",
        "paste_special":        "ctrl,alt,v",
        "select_all":           "ctrl,a",
        "find":                 "ctrl,f",
        "find_replace":         "ctrl,h",
        "go_to":                "ctrl,g",

        # Navigation
        "name_box":             "escape",     # Press Escape then F5 or Ctrl+G to open Go To
        "next_sheet":           "ctrl,page_down",
        "prev_sheet":           "ctrl,page_up",
        "go_to_beginning":      "ctrl,home",
        "go_to_end":            "ctrl,end",

        # Formatting
        "bold":                 "ctrl,b",
        "italic":               "ctrl,i",
        "underline":            "ctrl,u",
        "format_cells":         "ctrl,1",
        "autosum":              "alt,equal",

        # Insert
        "insert_row":           "ctrl,shift,plus",
        "delete_row":           "ctrl,minus",

        # Function keys
        "edit_cell":            "f2",
        "recalculate":          "f9",
        "save_alt":             "f12",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "excel.exe" in window_info.app_name.lower()
            or "excel" in window_info.title.lower()
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        """Excel is Win32/COM — UIA ScrollPattern works natively."""
        return "scroll_pattern"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        """Use clipboard for Excel cell input.

        Clipboard paste is more reliable than type_keys for cell addresses
        that contain colons (e.g. "A1:C10") or special characters.
        """
        return "clipboard"

    def requires_focus_restore(self) -> bool:
        """Excel does not steal focus after standard actions."""
        return False
