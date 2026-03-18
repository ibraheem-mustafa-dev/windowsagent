"""
Microsoft Excel app profile.

Excel is a Win32/COM application with strong UIA support. Key UIA elements:
- Name Box (AutomationId="NameBox"): cell address navigator
- Formula Bar (AutomationId="FormulaBar"): displays/edits cell contents
- Sheet tabs: TabItem controls at the bottom of the workbook
- Ribbon: standard toolbar buttons with known UIA names

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
        # Cell navigation
        "name box":             "Name Box",
        "cell address":         "Name Box",
        "cell reference":       "Name Box",
        "go to cell":           "Name Box",

        # Formula bar
        "formula bar":          "Formula Bar",
        "formula":              "Formula Bar",
        "cell content":         "Formula Bar",
        "cell value":           "Formula Bar",

        # Sheet tabs (generic — actual names vary per workbook)
        "sheet1":               "Sheet1",
        "sheet2":               "Sheet2",
        "sheet3":               "Sheet3",
        "new sheet":            "New sheet",
        "insert sheet":         "New sheet",

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
        "font color":           "Font Color",

        # Home tab — Alignment group
        "merge cells":          "Merge & Center",
        "wrap text":            "Wrap Text",
        "align left":           "Align Left",
        "align right":          "Align Right",
        "center":               "Center",

        # Home tab — Number group
        "currency format":      "Accounting Number Format",
        "percent":              "Percent Style",
        "comma style":          "Comma Style",

        # Home tab — Editing group
        "autosum":              "Sum",
        "sum":                  "Sum",
        "sort ascending":       "Sort Ascending",
        "sort descending":      "Sort Descending",
        "find and replace":     "Find & Select",
        "find":                 "Find & Select",

        # Insert tab
        "insert table":         "Table",
        "insert chart":         "Chart",
        "insert pivot table":   "PivotTable",

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
