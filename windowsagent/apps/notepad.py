"""
Notepad app profile.

Windows Notepad is the primary test target for WindowsAgent because it is:
- Always available on Windows 10/11
- Has excellent accessibility tree support
- Simple enough to be a reliable integration test baseline

This profile provides convenience methods wrapping common Notepad operations.
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import TYPE_CHECKING, Any, ClassVar

from windowsagent.apps.base import BaseAppProfile
from windowsagent.exceptions import ActionFailedError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import WindowInfo

logger = logging.getLogger(__name__)

# Notepad window appearance timeout
_WINDOW_TIMEOUT = 10.0  # seconds


class NotepadProfile(BaseAppProfile):
    """App profile for Windows Notepad (notepad.exe).

    Handles both classic Notepad (Windows 10) and the modernised version
    (Windows 11 with new title bar and tabs).
    """

    app_names: ClassVar[list[str]] = ["notepad.exe"]
    window_titles: ClassVar[list[str]] = ["Notepad", "- Notepad"]

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "notepad.exe" in window_info.app_name.lower()
            or "notepad" in window_info.title.lower()
        )


def open(
    filepath: str | None = None,
    config: Config | None = None,
) -> object:
    """Open Windows Notepad, optionally with a file.

    Args:
        filepath: Path to file to open, or None for a blank document.
        config: WindowsAgent configuration.

    Returns:
        pywinauto.Application connected to Notepad.

    Raises:
        ActionFailedError: If Notepad cannot be launched or found.
    """
    try:
        import pywinauto

        cmd = ["notepad.exe"]
        if filepath:
            cmd.append(filepath)

        logger.info("Opening Notepad%s", f" with {filepath!r}" if filepath else "")
        subprocess.Popen(cmd)

        # Wait for Notepad window to appear
        deadline = time.monotonic() + _WINDOW_TIMEOUT
        while time.monotonic() < deadline:
            try:
                app = pywinauto.Application(backend="uia")
                app.connect(title_re=".*Notepad.*", timeout=2.0)
                logger.debug("Connected to Notepad window")
                return app
            except Exception:
                time.sleep(0.3)

        raise ActionFailedError(
            action="open",
            reason=f"Notepad window did not appear within {_WINDOW_TIMEOUT}s",
            retryable=True,
        )

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="open_notepad",
            reason=f"Failed to launch Notepad: {exc}",
            retryable=True,
        ) from exc


def type_text(
    app: Any,
    text: str,
    config: Config,
) -> bool:
    """Type text into the main Notepad editing area.

    Uses ValuePattern if available (faster), otherwise keyboard simulation.

    Args:
        app: pywinauto.Application connected to Notepad.
        text: Text to type.
        config: WindowsAgent configuration.

    Returns:
        True if text was entered.

    Raises:
        ActionFailedError: If the edit control cannot be found.
    """
    try:
        from windowsagent.actor.uia_actor import focus as uia_focus
        from windowsagent.actor.uia_actor import type_text as uia_type
        from windowsagent.observer.uia import find_element, get_tree

        tree = get_tree(app)

        # Find the main text editing control
        edit = (
            find_element(tree, control_type="Edit")
            or find_element(tree, control_type="Document")
            or find_element(tree, name="Text Editor")
        )

        if edit is None:
            raise ActionFailedError(
                action="type",
                reason="Could not find edit control in Notepad",
                retryable=True,
            )

        uia_focus(edit, config)
        return uia_type(edit, text, config)

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="type_notepad",
            reason=f"Type text failed: {exc}",
            retryable=True,
        ) from exc


def save(
    app: Any,
    filepath: str | None = None,
    config: Config | None = None,
) -> bool:
    """Save the current Notepad document.

    If filepath is None, uses Ctrl+S (save existing or trigger Save dialog).
    If filepath is provided, uses Ctrl+Shift+S (Save As) and fills in the path.

    Args:
        app: pywinauto.Application connected to Notepad.
        filepath: Target file path for Save As, or None for plain Ctrl+S.
        config: WindowsAgent configuration.

    Returns:
        True if save succeeded.
    """
    try:
        from windowsagent.actor.input_actor import hotkey, press_key, type_text

        main_win = app.top_window()
        main_win.set_focus()
        time.sleep(0.1)

        if filepath:
            hotkey("ctrl", "shift", "s")  # Save As
        else:
            hotkey("ctrl", "s")

        time.sleep(0.5)

        if filepath:
            # Type the path in the Save As dialog
            hotkey("ctrl", "a")  # Select all in filename field
            time.sleep(0.1)
            type_text(filepath)
            time.sleep(0.1)
            press_key("enter")
            time.sleep(0.5)

            # Handle overwrite confirmation if it appears
            try:
                import pywinauto
                confirm_app = pywinauto.Application(backend="uia")
                confirm_app.connect(title_re=".*Confirm.*|.*Replace.*|.*already exists.*", timeout=1.5)
                main_confirm = confirm_app.top_window()
                # Click Yes/Replace
                for btn_name in ("Yes", "Replace", "OK"):
                    try:
                        btn = main_confirm.child_window(title=btn_name, control_type="Button")
                        btn.click()
                        break
                    except Exception:
                        pass
            except Exception:
                pass  # No confirmation dialog

        logger.debug("Saved Notepad document%s", f" as {filepath!r}" if filepath else "")
        return True

    except Exception as exc:
        raise ActionFailedError(
            action="save",
            reason=f"Save failed: {exc}",
            retryable=True,
        ) from exc


def select_all(app: Any, config: Config | None = None) -> bool:
    """Select all text in the current Notepad document.

    Args:
        app: pywinauto.Application connected to Notepad.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    try:
        from windowsagent.actor.input_actor import hotkey
        main_win = app.top_window()
        main_win.set_focus()
        hotkey("ctrl", "a")
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="select_all",
            reason=f"Select all failed: {exc}",
            retryable=True,
        ) from exc


def get_text(app: Any, config: Config | None = None) -> str:
    """Read all text from the Notepad editing area.

    Tries ValuePattern first, then falls back to Ctrl+A + Ctrl+C + clipboard.

    Args:
        app: pywinauto.Application connected to Notepad.
        config: WindowsAgent configuration.

    Returns:
        Current document text.

    Raises:
        ActionFailedError: If text cannot be retrieved.
    """
    try:
        from windowsagent.observer.uia import find_element, get_tree

        tree = get_tree(app, force_refresh=True)
        edit = (
            find_element(tree, control_type="Edit")
            or find_element(tree, control_type="Document")
        )

        if edit and edit.value:
            return edit.value

        # Fall back to clipboard method
        from windowsagent.actor.clipboard import get_text as clipboard_get
        from windowsagent.actor.input_actor import hotkey

        main_win = app.top_window()
        main_win.set_focus()
        hotkey("ctrl", "a")
        time.sleep(0.05)
        hotkey("ctrl", "c")
        time.sleep(0.1)

        text = clipboard_get()
        logger.debug("Got Notepad text via clipboard (%d chars)", len(text))
        return text

    except Exception as exc:
        raise ActionFailedError(
            action="get_text",
            reason=f"Could not read Notepad text: {exc}",
            retryable=True,
        ) from exc


def clear(app: Any, config: Config | None = None) -> bool:
    """Clear all text from the Notepad document.

    Args:
        app: pywinauto.Application connected to Notepad.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    try:
        from windowsagent.actor.input_actor import hotkey, press_key

        main_win = app.top_window()
        main_win.set_focus()
        hotkey("ctrl", "a")
        time.sleep(0.05)
        press_key("delete")
        logger.debug("Cleared Notepad content")
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="clear",
            reason=f"Clear failed: {exc}",
            retryable=True,
        ) from exc
