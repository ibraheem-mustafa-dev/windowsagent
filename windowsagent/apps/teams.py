"""
Microsoft Teams app profile.

New Teams (2023+) is a WebView2/Electron hybrid. The navigation sidebar
has good UIA support; message content is WebView2 and requires OCR.

Known quirks:
- Ctrl+K is the universal 'Go To' command — most reliable navigation entry point.
- Compose box element name may vary between Teams versions ('Type a new message'
  or 'New message'). Always observe first to confirm.
- In-call controls (mute, camera, hang up) are exposed as named UIA buttons.
- Focus can jump unexpectedly when a notification toast appears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class TeamsProfile(BaseAppProfile):
    """App profile for Microsoft Teams (ms-teams.exe or Teams.exe)."""

    app_names: ClassVar[list[str]] = ["ms-teams.exe", "teams.exe", "msteams.exe"]
    window_titles: ClassVar[list[str]] = ["Microsoft Teams", "Teams"]

    known_elements: ClassVar[dict[str, str]] = {
        # Navigation
        "search":                       "Search Microsoft Teams",
        "go to":                        "Search Microsoft Teams",
        "search bar":                   "Search Microsoft Teams",
        "find channel":                 "Find a channel, name, or file",
        "go to input":                  "Find a channel, name, or file",

        # Compose
        "compose":                      "Type a new message",
        "message input":                "Type a new message",
        "type a message":               "Type a new message",
        "new message":                  "Type a new message",
        "message box":                  "Type a new message",

        # Nav tabs (left sidebar)
        "activity":                     "Activity",
        "chat":                         "Chat",
        "teams":                        "Teams",
        "calendar":                     "Calendar",
        "calls":                        "Calls",
        "files":                        "Files",

        # In-call controls
        "mute":                         "Mute",
        "unmute":                       "Unmute",
        "camera":                       "Turn camera on",
        "turn off camera":              "Turn camera off",
        "hang up":                      "Leave",
        "end call":                     "Leave",
        "raise hand":                   "Raise your hand",
        "share screen":                 "Share",
        "more actions":                 "More actions",
        "send message":                 "Send message",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        "go_to":                "ctrl,k",
        "search":               "ctrl,f",
        "new_chat":             "ctrl,n",
        "activity":             "ctrl,1",
        "chat":                 "ctrl,2",
        "teams":                "ctrl,3",
        "calendar":             "ctrl,4",
        "calls":                "ctrl,5",
        "files":                "ctrl,6",
        "mute_toggle":          "ctrl,shift,m",
        "camera_toggle":        "ctrl,shift,o",
        "raise_hand":           "ctrl,shift,k",
        "end_call":             "ctrl,shift,h",
        "accept_call":          "ctrl,shift,a",
        "decline_call":         "ctrl,shift,d",
        "mark_as_read":         "ctrl,shift,u",
        "settings":             "ctrl,comma",
        "zoom_in":              "ctrl,plus",
        "zoom_out":             "ctrl,minus",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            any(name in window_info.app_name.lower() for name in ("ms-teams", "teams.exe", "msteams"))
            or "microsoft teams" in window_info.title.lower()
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        return "webview2"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        # Teams compose box does not support ValuePattern — always use clipboard paste
        return "clipboard"

    def requires_focus_restore(self) -> bool:
        # Teams toasts steal focus unpredictably
        return True
