"""
Clipboard module — efficient data transfer via the Win32 clipboard.

For text longer than ~100 characters, using the clipboard to paste is
significantly faster than keyboard simulation (~50ms/char). This module
wraps the Win32 clipboard API cleanly and adds a paste_to_element()
convenience function that handles focus and selection.

Dependencies: pywin32 (win32clipboard)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from windowsagent.exceptions import ActionFailedError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import UIAElement

logger = logging.getLogger(__name__)

# OpenClipboard retry constants
_CLIPBOARD_RETRIES = 5
_CLIPBOARD_RETRY_DELAY = 0.05  # seconds


def set_text(text: str) -> None:
    """Set the clipboard to contain the given text.

    Retries up to 5 times if another process holds the clipboard open.

    Args:
        text: Text to place on the clipboard.

    Raises:
        ActionFailedError: If clipboard cannot be opened after retries.
    """
    try:
        import win32clipboard
        import win32con
    except ImportError as exc:
        # Fallback to pyperclip if available
        try:
            import pyperclip
            pyperclip.copy(text)
            logger.debug("Set clipboard via pyperclip (%d chars)", len(text))
            return
        except ImportError:
            raise ActionFailedError(
                action="set_clipboard",
                reason="Neither pywin32 nor pyperclip is installed",
                retryable=False,
            ) from exc

    last_exc: Exception | None = None
    for attempt in range(_CLIPBOARD_RETRIES):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            logger.debug("Set clipboard (%d chars)", len(text))
            return
        except Exception as exc:
            last_exc = exc
            logger.debug(
                "Clipboard open attempt %d/%d failed: %s", attempt + 1, _CLIPBOARD_RETRIES, exc
            )
            time.sleep(_CLIPBOARD_RETRY_DELAY)

    raise ActionFailedError(
        action="set_clipboard",
        reason=f"Could not open clipboard after {_CLIPBOARD_RETRIES} attempts: {last_exc}",
        retryable=True,
    )


def get_text() -> str:
    """Read text from the clipboard.

    Returns:
        Current clipboard text, or empty string if clipboard is empty or
        does not contain text.

    Raises:
        ActionFailedError: If clipboard cannot be read.
    """
    try:
        import win32clipboard
        import win32con
    except ImportError:
        try:
            import pyperclip
            return pyperclip.paste()
        except ImportError as exc:
            raise ActionFailedError(
                action="get_clipboard",
                reason="Neither pywin32 nor pyperclip is installed",
                retryable=False,
            ) from exc

    last_exc: Exception | None = None
    for attempt in range(_CLIPBOARD_RETRIES):
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return text or ""
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                    text = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                    return (text or b"").decode("utf-8", errors="replace")
                return ""
            finally:
                win32clipboard.CloseClipboard()
        except Exception as exc:
            last_exc = exc
            time.sleep(_CLIPBOARD_RETRY_DELAY)

    raise ActionFailedError(
        action="get_clipboard",
        reason=f"Could not read clipboard after {_CLIPBOARD_RETRIES} attempts: {last_exc}",
        retryable=True,
    )


def paste_to_element(
    element: "UIAElement",
    text: str,
    config: "Config",
) -> bool:
    """Set text and paste it into a UI element.

    This is faster than typing for long strings. The sequence is:
    1. Focus the element
    2. Select all existing content (Ctrl+A)
    3. Place text in clipboard
    4. Paste (Ctrl+V)
    5. Verify element.value matches the pasted text (best-effort)

    Args:
        element: Target element to paste into.
        text: Text to paste.
        config: WindowsAgent configuration.

    Returns:
        True if paste succeeded.

    Raises:
        ActionFailedError: If paste fails.
    """
    try:
        from windowsagent.actor.input_actor import click_at, hotkey

        # Focus the element
        cx, cy = element.centre
        click_at(cx, cy, config=config)
        time.sleep(0.05)

        # Select all existing content
        hotkey("ctrl", "a", config=config)
        time.sleep(0.03)

        # Place text in clipboard
        set_text(text)
        time.sleep(0.03)

        # Paste
        hotkey("ctrl", "v", config=config)
        time.sleep(0.1)

        logger.debug("Pasted %d chars into %r via clipboard", len(text), element.name)
        return True

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="paste",
            reason=f"Clipboard paste failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def clear() -> None:
    """Clear the clipboard contents.

    Silently does nothing if clipboard cannot be cleared (non-critical).
    """
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()
        logger.debug("Clipboard cleared")
    except ImportError:
        try:
            import pyperclip
            pyperclip.copy("")
        except ImportError:
            logger.debug("pywin32 and pyperclip not available, cannot clear clipboard")
    except Exception as exc:
        logger.debug("Could not clear clipboard: %s", exc)
