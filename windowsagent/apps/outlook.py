"""
Microsoft Outlook app profile.

New Outlook (Windows 11) is a WebView2-based application that runs as
olk.exe or inside msedgewebview2.exe. It has several specific automation
challenges:

1. Email list is virtualised: only ~15 emails visible in UIA tree at once
2. Reading pane steals keyboard focus when an email is clicked
3. The compose window is a separate top-level window
4. Sent/Delete actions are sensitive and require confirmation

This profile inherits WebView2Profile for scroll/focus handling and adds
Outlook-specific operations.
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import TYPE_CHECKING, Any, ClassVar

from windowsagent.apps.webview2 import WebView2Profile, find_virtualised_item, scroll_content
from windowsagent.exceptions import ActionFailedError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import UIAElement, WindowInfo

logger = logging.getLogger(__name__)

# Outlook process names (new Outlook)
OUTLOOK_PROCESS_NAMES = frozenset(["olk.exe", "outlook.exe", "msedgewebview2.exe"])

_WINDOW_TIMEOUT = 15.0  # Outlook takes longer to load


class OutlookProfile(WebView2Profile):
    """App profile for Microsoft Outlook (new Outlook, WebView2-based).

    Inherits WebView2Profile for scroll handling. Adds Outlook-specific
    email list navigation and reading pane management.

    Known quirks:
    - Email list is virtualised: only ~15 emails in UIA tree at once.
    - Reading pane steals keyboard focus when an email is clicked.
    - Compose window is a separate top-level window.
    - Send/Delete actions are sensitive and require confirmation.
    - Ctrl+F is Forward (not Find) — search is Ctrl+E or F3.
    """

    app_names: ClassVar[list[str]] = ["olk.exe", "outlook.exe"]
    window_titles: ClassVar[list[str]] = ["Outlook", "Mail"]

    # Verified UIA element names (observed in New Outlook 2024-2025)
    known_elements: ClassVar[dict[str, str]] = {
        # Toolbar actions
        "new mail":                 "New mail",
        "new email":                "New mail",
        "compose":                  "New mail",
        "new message":              "New mail",
        "reply":                    "Reply",
        "reply button":             "Reply",
        "reply all":                "Reply all",
        "forward":                  "Forward",
        "forward button":           "Forward",
        "delete":                   "Delete",
        "delete button":            "Delete",
        "archive":                  "Archive",
        "archive button":           "Archive",
        "flag":                     "Flag",
        "pin":                      "Pin",
        "mark as read":             "Mark as read",
        "mark as unread":           "Mark as unread",
        "move to":                  "Move to",
        "more actions":             "More actions",
        "snooze":                   "Snooze",

        # Search
        "search":                   "Search",
        "search bar":               "Search",
        "search box":               "Search",

        # Navigation pane (left sidebar)
        "inbox":                    "Inbox",
        "drafts":                   "Drafts",
        "sent items":               "Sent Items",
        "sent":                     "Sent Items",
        "junk":                     "Junk Email",
        "junk email":               "Junk Email",
        "deleted items":            "Deleted Items",
        "trash":                    "Deleted Items",
        "folders":                  "Folders",

        # Bottom nav
        "mail":                     "Mail",
        "mail tab":                 "Mail",
        "calendar":                 "Calendar",
        "calendar tab":             "Calendar",
        "people":                   "People",
        "contacts":                 "People",
        "to do":                    "To Do",
        "tasks":                    "To Do",

        # Compose window
        "to field":                 "To",
        "to":                       "To",
        "cc field":                 "Cc",
        "cc":                       "Cc",
        "bcc field":                "Bcc",
        "bcc":                      "Bcc",
        "subject field":            "Subject",
        "subject":                  "Subject",
        "message body":             "Message body",
        "body":                     "Message body",
        "send":                     "Send",
        "send button":              "Send",
        "discard":                  "Discard",
        "attach":                   "Attach file",
        "attach file":              "Attach file",
        "insert":                   "Insert",
    }

    shortcuts: ClassVar[dict[str, str]] = {
        # Compose & reply
        "new_mail":             "ctrl,n",
        "reply":                "ctrl,r",
        "reply_all":            "ctrl,shift,r",
        "forward":              "ctrl,f",
        "send":                 "ctrl,enter",
        "save_draft":           "ctrl,s",

        # Navigation
        "mail":                 "ctrl,1",
        "calendar":             "ctrl,2",
        "people":               "ctrl,3",
        "to_do":                "ctrl,4",
        "search":               "ctrl,e",
        "search_alt":           "f3",
        "go_to_folder":         "ctrl,y",

        # Message actions
        "delete":               "Delete",
        "permanent_delete":     "shift,Delete",
        "mark_read":            "ctrl,q",
        "mark_unread":          "ctrl,u",
        "flag":                 "Insert",
        "archive":              "backspace",

        # Reading
        "open_message":         "enter",
        "close_message":        "escape",
        "next_message":         "down",
        "prev_message":         "up",
        "address_book":         "ctrl,shift,b",
        "print":                "ctrl,p",
        "select_all":           "ctrl,a",
        "find_in_message":      "f4",
        "zoom_in":              "ctrl,plus",
        "zoom_out":             "ctrl,minus",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        return any(
            name in window_info.app_name.lower()
            for name in ("olk.exe", "outlook.exe", "mail")
        ) or "outlook" in window_info.title.lower()

    def requires_focus_restore(self) -> bool:
        # Outlook reading pane steals focus — agent restores after each action
        return True

    def get_text_input_strategy(self) -> str:  # type: ignore[override]
        # Outlook compose fields work best with clipboard paste
        return "clipboard"

    def on_before_act(self, action: str, element: UIAElement | None) -> None:
        """Ensure target panel has focus before acting.

        Outlook's reading pane aggressively grabs focus. Before clicking in
        the email list or toolbar, we need to make sure focus isn't trapped
        in the reading pane.
        """
        if element and action == "click":
            # If the element is in the email list or toolbar (not reading pane),
            # pressing Escape first exits the reading pane focus trap
            if element.control_type in ("ListItem", "Button", "MenuItem"):
                try:
                    from windowsagent.actor.input_actor import press_key
                    press_key("escape", config=None)
                except Exception:
                    pass


def open(config: Config | None = None) -> Any:
    """Open Microsoft Outlook.

    Attempts to connect to an already-running instance first, then launches.

    Args:
        config: WindowsAgent configuration.

    Returns:
        pywinauto.Application connected to Outlook.

    Raises:
        ActionFailedError: If Outlook cannot be launched or found.
    """
    try:
        import pywinauto

        # Try connecting to already-running instance
        for process_name in ("olk.exe", "outlook.exe"):
            try:
                app = pywinauto.Application(backend="uia")
                app.connect(path=process_name, timeout=2.0)
                logger.debug("Connected to existing Outlook instance (%s)", process_name)
                return app
            except Exception:
                pass

        # Launch Outlook
        logger.info("Launching Microsoft Outlook")
        subprocess.Popen(["olk.exe"])

        deadline = time.monotonic() + _WINDOW_TIMEOUT
        while time.monotonic() < deadline:
            try:
                app = pywinauto.Application(backend="uia")
                app.connect(title_re=".*Outlook.*|.*Mail.*", timeout=3.0)
                return app
            except Exception:
                time.sleep(0.5)

        raise ActionFailedError(
            action="open_outlook",
            reason=f"Outlook window did not appear within {_WINDOW_TIMEOUT}s",
            retryable=True,
        )

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="open_outlook",
            reason=f"Failed to open Outlook: {exc}",
            retryable=True,
        ) from exc


def scroll_email_list(
    app: Any,
    direction: str,
    config: Config,
) -> bool:
    """Scroll the email list in Outlook.

    Uses WebView2 keyboard scroll strategy because mouse wheel does not
    reach the inner email list content reliably.

    Args:
        app: pywinauto.Application connected to Outlook.
        direction: "up" or "down".
        config: WindowsAgent configuration.

    Returns:
        True if scroll was detected.
    """
    return scroll_content(app, direction, 1, config)


def find_email(
    app: Any,
    subject: str,
    config: Config,
) -> UIAElement | None:
    """Find an email in the list by subject.

    Searches visible UIA elements first, then scrolls to find virtualised items.

    Args:
        app: pywinauto.Application connected to Outlook.
        subject: Full or partial email subject to search for.
        config: WindowsAgent configuration.

    Returns:
        UIAElement for the email item, or None if not found.
    """
    return find_virtualised_item(app, subject, config, max_scrolls=20)


def click_email(
    app: Any,
    subject: str,
    config: Config,
) -> bool:
    """Click an email to select it and open it in the reading pane.

    IMPORTANT: After clicking an email, focus shifts to the reading pane.
    If you need to continue working with the email list, call
    re-focus logic afterwards.

    Args:
        app: pywinauto.Application connected to Outlook.
        subject: Full or partial email subject.
        config: WindowsAgent configuration.

    Returns:
        True if email was clicked.
    """
    try:
        from windowsagent.actor.uia_actor import click

        element = find_email(app, subject, config)
        if element is None:
            raise ActionFailedError(
                action="click_email",
                reason=f"Email with subject {subject!r} not found",
                retryable=True,
            )

        result = click(element, config)
        if result:
            # Wait for reading pane to load
            time.sleep(0.5)
        return result

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="click_email",
            reason=f"Could not click email {subject!r}: {exc}",
            retryable=True,
        ) from exc


def get_reading_pane_text(app: Any, config: Config) -> str:
    """Extract text from the Outlook reading pane.

    The reading pane is WebView2 content. Uses OCR as the primary method
    because the UIA tree for reading pane content is often sparse.

    Args:
        app: pywinauto.Application connected to Outlook.
        config: WindowsAgent configuration.

    Returns:
        Text content of the reading pane (may be incomplete for very long emails).
    """
    try:
        from windowsagent.observer.ocr import extract_text
        from windowsagent.observer.screenshot import capture_window

        main_win = app.top_window()
        screenshot = capture_window(main_win.handle, config)
        results = extract_text(screenshot, config)
        full_text = " ".join(r.text for r in results)
        logger.debug("Reading pane text extracted (%d chars)", len(full_text))
        return full_text

    except Exception as exc:
        raise ActionFailedError(
            action="get_reading_pane_text",
            reason=f"Could not read reading pane: {exc}",
            retryable=True,
        ) from exc
