"""
Visual Studio Code app profile.

VS Code is an Electron app with good UIA accessibility support. Most panels
expose named elements. Terminal, editor, and sidebar all respond well to
keyboard navigation and UIA interaction.

Known quirks:
- Backtick (Ctrl+`) as a shortcut conflicts with PowerShell escaping.
  Use VK_OEM_3 (0xC0) for the terminal toggle shortcut.
- Element names may change between VS Code major versions.
- Quick Open input element is named 'input' when the palette is open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class VSCodeProfile(BaseAppProfile):
    """App profile for Visual Studio Code (Code.exe).

    Handles the Electron-based editor. Element names are from the Chromium
    accessibility tree as exposed by Electron's UIA bridge.
    """

    app_names: ClassVar[list[str]] = ["code.exe", "code - insiders.exe"]
    window_titles: ClassVar[list[str]] = ["Visual Studio Code", "- Visual Studio Code"]

    # Verified UIA element names for VS Code panels
    known_elements: ClassVar[dict[str, str]] = {
        # Editor
        "editor":                   "editor content",
        "text editor":              "editor content",
        "code editor":              "editor content",
        "editor content":           "editor content",

        # Quick Open / Command Palette (only present when open)
        "quick open":               "input",
        "command palette":          "input",
        "file search":              "input",
        "go to file":               "input",
        "search input":             "input",
        "input":                    "input",

        # Sidebar panels
        "explorer":                 "Explorer",
        "file explorer":            "Explorer",
        "search":                   "Search",
        "source control":           "Source Control",
        "git":                      "Source Control",
        "extensions":               "Extensions",
        "debug":                    "Run and Debug",
        "run and debug":            "Run and Debug",

        # Terminal
        "terminal":                 "Terminal",
        "integrated terminal":      "Terminal",

        # Status bar
        "status bar":               "workbench.parts.statusbar",
        "bottom bar":               "workbench.parts.statusbar",

        # Activity bar (left sidebar icons)
        "activity bar":             "Activity Bar",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        "quick_open":               "ctrl,p",
        "go_to_file":               "ctrl,p",
        "command_palette":          "ctrl,shift,p",
        "new_terminal":             "ctrl,shift,oem_3",   # Ctrl+` (OEM_3 avoids PS escaping)
        "toggle_terminal":          "ctrl,oem_3",
        "toggle_sidebar":           "ctrl,b",
        "toggle_panel":             "ctrl,j",
        "find_in_file":             "ctrl,f",
        "find_in_project":          "ctrl,shift,f",
        "go_to_line":               "ctrl,g",
        "save":                     "ctrl,s",
        "save_all":                 "ctrl,k ctrl,s",
        "format_document":          "shift,alt,f",
        "close_tab":                "ctrl,w",
        "reopen_tab":               "ctrl,shift,t",
        "split_editor":             "ctrl,backslash",
        "zen_mode":                 "ctrl,k z",
        "next_tab":                 "ctrl,tab",
        "prev_tab":                 "ctrl,shift,tab",
        "go_back":                  "alt,Left",
        "go_forward":               "alt,Right",
        "rename_symbol":            "f2",
        "peek_definition":          "alt,f12",
        "go_to_definition":         "f12",
        "toggle_comment":           "ctrl,slash",
        "select_line":              "ctrl,l",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "code.exe" in window_info.app_name.lower()
            or "visual studio code" in window_info.title.lower()
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        # VS Code editor uses webview2-style scrolling
        return "webview2"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        # Terminal and editor accept keyboard input; use clipboard for reliability
        return "clipboard"
