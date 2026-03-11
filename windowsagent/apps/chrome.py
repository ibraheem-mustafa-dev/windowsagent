"""
Google Chrome app profile.

Chrome's UIA tree is shallow — most page content is not exposed as named
elements. The profile handles navigation, tab management, and delegates
page interaction to OCR + coordinate-based clicking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class ChromeProfile(BaseAppProfile):
    """App profile for Google Chrome (chrome.exe).

    Known quirks:
    - Page body content is not in the UIA tree. Use OCR for page text.
    - Address bar UIA name is 'Address and search bar'.
    - Tab bar elements are exposed but unreliable for multi-tab navigation.
    - Keyboard navigation (Ctrl+L, Ctrl+T, etc.) is the most reliable method.
    """

    app_names: ClassVar[list[str]] = ["chrome.exe"]
    window_titles: ClassVar[list[str]] = ["Google Chrome", "- Google Chrome"]

    # Verified UIA element names (observed in Chrome 120+)
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
        "new tab button":           "New Tab",
        "close tab":                "Close",
        "bookmark":                 "Bookmark this tab",
        "settings":                 "Customize and control Google Chrome",
        "settings menu":            "Customize and control Google Chrome",
        "downloads":                "Downloads",
        "find bar":                 "Find",
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
        "bookmark":          "ctrl,d",
        "history":           "ctrl,h",
        "downloads":         "ctrl,j",
        "zoom_in":           "ctrl,plus",
        "zoom_out":          "ctrl,minus",
        "zoom_reset":        "ctrl,0",
        "new_window":        "ctrl,n",
        "new_incognito":     "ctrl,shift,n",
        "print":             "ctrl,p",
        "save_page":         "ctrl,s",
        "view_source":       "ctrl,u",
        "focus_first_tab":   "ctrl,1",
        "focus_last_tab":    "ctrl,9",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "chrome.exe" in window_info.app_name.lower()
            or "google chrome" in window_info.title.lower()
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        # Chrome page content is WebView2-equivalent — use keyboard scroll
        return "webview2"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        # Address bar uses value_pattern; page inputs vary — default to clipboard for safety
        return "clipboard"
