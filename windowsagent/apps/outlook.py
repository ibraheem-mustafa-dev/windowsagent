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
from typing import TYPE_CHECKING

from windowsagent.apps.webview2 import WebView2Profile, scroll_content, find_virtualised_item
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
    """

    app_names: list[str] = ["olk.exe", "outlook.exe"]
    window_titles: list[str] = ["Outlook", "Mail"]

    def is_match(self, window_info: "WindowInfo") -> bool:
        return any(
            name in window_info.app_name.lower()
            for name in ("olk.exe", "outlook.exe", "mail")
        ) or "outlook" in window_info.title.lower()

    def requires_focus_restore(self) -> bool:
        # Outlook reading pane steals focus — always re-validate
        return True


def open(config: "Config | None" = None) -> "object":
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
    app: "object",
    direction: str,
    config: "Config",
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
    app: "object",
    subject: str,
    config: "Config",
) -> "UIAElement | None":
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
    app: "object",
    subject: str,
    config: "Config",
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


def get_reading_pane_text(app: "object", config: "Config") -> str:
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
        from windowsagent.observer.screenshot import capture_window
        from windowsagent.observer.ocr import extract_text

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
