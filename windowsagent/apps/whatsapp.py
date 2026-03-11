"""
WhatsApp Web app profile.

WhatsApp Web runs inside Edge or Chrome as a React SPA. All message content
is WebView2 — use OCR to read it. Sending messages requires clipboard paste
into the compose box.

Known quirks:
- All content is WebView2; UIA tree is nearly empty for message content.
- Search shortcut is Ctrl+F (opens chat search, not find-in-page).
- The compose box element name may be 'Type a message' or vary by version.
- Arabic text must use clipboard paste — keyboard simulation drops RTL chars.
- Multi-device mode must be enabled on phone; QR code required on first use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo

# WhatsApp Web is always loaded inside a browser window
WHATSAPP_URL = "web.whatsapp.com"


class WhatsAppWebProfile(BaseAppProfile):
    """App profile for WhatsApp Web (loaded in Edge or Chrome).

    Matched by window title containing 'WhatsApp' — not by process name,
    since it runs inside the browser host.
    """

    app_names: ClassVar[list[str]] = []   # Matched by title, not process
    window_titles: ClassVar[list[str]] = ["WhatsApp", "WhatsApp Web"]

    known_elements: ClassVar[dict[str, str]] = {
        # Search / navigation
        "search":               "Search or start new chat",
        "search bar":           "Search or start new chat",
        "search chats":         "Search or start new chat",
        "new chat":             "New chat",
        "start new chat":       "New chat",

        # Compose
        "compose":              "Type a message",
        "message input":        "Type a message",
        "type a message":       "Type a message",
        "message box":          "Type a message",
        "reply box":            "Type a message",

        # Actions
        "attach":               "Attach",
        "emoji":                "Emoji",
        "send":                 "Send",
        "voice message":        "Voice message",
        "more options":         "More options",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        "search":               "ctrl,f",
        "new_chat":             "ctrl,n",
        "archive":              "ctrl,e",
        "mark_unread":          "ctrl,u",
        "mute":                 "ctrl,shift,m",
        "next_unread":          "ctrl,shift,u",
        "next_chat":            "ctrl,Tab",
        "prev_chat":            "ctrl,shift,Tab",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return "whatsapp" in window_info.title.lower()

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        return "webview2"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        # Must use clipboard — keyboard drops Arabic and special chars
        return "clipboard"
