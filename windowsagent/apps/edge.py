"""
Microsoft Edge app profile.

Edge has the same UIA structure as Chrome (both are Chromium-based).
Additional quirk: the Copilot sidebar can shift element positions and
interfere with coordinate-based clicking — close it before acting if needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class EdgeProfile(BaseAppProfile):
    """App profile for Microsoft Edge (msedge.exe).

    Known quirks:
    - Copilot sidebar (Ctrl+Shift+E) can narrow the viewport and shift elements.
    - UIA element names are identical to Chrome for all navigation controls.
    - PWAs installed via Edge appear as their own app_name (e.g. 'msedge.exe' with app flags).
    - WebView2 content is not accessible via UIA — use OCR.
    """

    app_names: ClassVar[list[str]] = ["msedge.exe", "microsoft edge"]
    window_titles: ClassVar[list[str]] = ["Microsoft Edge", "- Microsoft Edge"]

    # Verified UIA element names (same as Chrome for navigation elements)
    known_elements: ClassVar[dict[str, str]] = {
        "address bar":              "Address and search bar",
        "url bar":                  "Address and search bar",
        "address and search bar":   "Address and search bar",
        "omnibox":                  "Address and search bar",
        "back":                     "Back",
        "back button":              "Back",
        "forward":                  "Forward",
        "forward button":           "Forward",
        "reload":                   "Reload",
        "refresh":                  "Reload",
        "new tab":                  "New Tab",
        "close tab":                "Close",
        "settings":                 "Settings and more",
        "settings menu":            "Settings and more",
        "hamburger menu":           "Settings and more",
        "sidebar":                  "Sidebar",
        "copilot":                  "Copilot",
        "find bar":                 "Find",
        "reading view":             "Enter Immersive Reader",
        "collections":              "Collections",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        "address_bar":       "ctrl,l",
        "new_tab":           "ctrl,t",
        "close_tab":         "ctrl,w",
        "reopen_tab":        "ctrl,shift,t",
        "next_tab":          "ctrl,tab",
        "prev_tab":          "ctrl,shift,tab",
        "reload":            "ctrl,r",
        "hard_reload":       "ctrl,shift,r",
        "find":              "ctrl,f",
        "back":              "alt,Left",
        "forward":           "alt,Right",
        "dev_tools":         "f12",
        "sidebar":           "ctrl,shift,e",
        "reading_view":      "f9",
        "collections":       "ctrl,shift,y",
        "new_window":        "ctrl,n",
        "new_inprivate":     "ctrl,shift,n",
        "print":             "ctrl,p",
        "zoom_in":           "ctrl,plus",
        "zoom_out":          "ctrl,minus",
        "zoom_reset":        "ctrl,0",
        "focus_first_tab":   "ctrl,1",
        "focus_last_tab":    "ctrl,9",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "msedge.exe" in window_info.app_name.lower()
            or "microsoft edge" in window_info.title.lower()
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        return "webview2"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        return "clipboard"
