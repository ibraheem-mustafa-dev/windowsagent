"""
PowerShell / Windows Terminal app profile.

Covers both Windows Terminal (wt.exe) and legacy PowerShell windows.
Terminal text content is not in the UIA tree — use OCR to read output.

Known quirks:
- Windows Terminal paste shortcut is Ctrl+Shift+V (not Ctrl+V).
- Legacy PowerShell console (conhost.exe) uses Ctrl+V or right-click paste.
- Output text is not exposed via UIA — use OCR or /shell endpoint instead.
- The /shell endpoint is preferred over UIA terminal interaction for
  getting command output back to the agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class PowerShellProfile(BaseAppProfile):
    """App profile for Windows Terminal (wt.exe) and PowerShell (pwsh.exe / powershell.exe)."""

    app_names: ClassVar[list[str]] = [
        "windowsterminal.exe",
        "wt.exe",
        "pwsh.exe",
        "powershell.exe",
    ]
    window_titles: ClassVar[list[str]] = [
        "Windows PowerShell",
        "PowerShell",
        "Windows Terminal",
    ]

    known_elements: ClassVar[dict[str, str]] = {
        "terminal":             "Terminal",
        "terminal window":      "Terminal",
        "console":              "Terminal",
        "input":                "Terminal",
        "command input":        "Terminal",
        "tab bar":              "TabBar",
        "new tab":              "New tab",
        "close tab":            "Close tab",
        "settings":             "Settings",
        "search":               "Search",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        # Windows Terminal shortcuts
        "paste":                "ctrl,shift,v",      # WT paste (NOT ctrl+v)
        "copy":                 "ctrl,shift,c",
        "new_tab":              "ctrl,shift,t",
        "close_tab":            "ctrl,shift,w",
        "new_pane":             "alt,shift,d",
        "new_window":           "ctrl,shift,n",
        "find":                 "ctrl,shift,f",
        "zoom_in":              "ctrl,plus",
        "zoom_out":             "ctrl,minus",
        "zoom_reset":           "ctrl,0",
        "next_tab":             "ctrl,tab",
        "prev_tab":             "ctrl,shift,tab",
        "scroll_up":            "ctrl,shift,Up",
        "scroll_down":          "ctrl,shift,Down",
        "scroll_page_up":       "ctrl,shift,Prior",
        "scroll_page_down":     "ctrl,shift,Next",
        "focus_pane_up":        "alt,Up",
        "focus_pane_down":      "alt,Down",
        "settings":             "ctrl,comma",
        # Shell shortcuts (work regardless of terminal host)
        "interrupt":            "ctrl,c",
        "clear_screen":         "ctrl,l",
        "previous_command":     "Up",
        "next_command":         "Down",
        "home":                 "Home",
        "end":                  "End",
        "autocomplete":         "tab",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return any(
            name in window_info.app_name.lower()
            for name in ("windowsterminal", "pwsh", "powershell", "wt.exe")
        ) or any(
            title in window_info.title.lower()
            for title in ("powershell", "windows terminal", "command prompt")
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        return "keyboard"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        # Windows Terminal uses clipboard paste (Ctrl+Shift+V)
        return "clipboard"
