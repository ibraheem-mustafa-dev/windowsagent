"""
File Explorer app profile.

Provides fast, reliable automation for Windows File Explorer (explorer.exe).

Key design decisions:
- Navigate via address bar typing (faster than clicking through folders)
- Use keyboard shortcuts where possible (F2 for rename, Delete for delete)
- delete_item() moves to Recycle Bin (NEVER permanently deletes)
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
    from windowsagent.observer.uia import UIAElement, WindowInfo

logger = logging.getLogger(__name__)

_WINDOW_TIMEOUT = 10.0  # seconds to wait for File Explorer to appear


class FileExplorerProfile(BaseAppProfile):
    """App profile for Windows File Explorer (explorer.exe)."""

    app_names: ClassVar[list[str]] = ["explorer.exe"]
    window_titles: ClassVar[list[str]] = ["File Explorer", "Windows Explorer"]

    def is_match(self, window_info: WindowInfo) -> bool:
        return (
            "explorer.exe" in window_info.app_name.lower()
            and window_info.title not in ("", "Program Manager")
        )


def open(
    path: str | None = None,
    config: Config | None = None,
) -> object:
    """Open File Explorer, optionally at a specific path.

    Args:
        path: Folder path to open, or None for the default location.
        config: WindowsAgent configuration.

    Returns:
        pywinauto.Application connected to File Explorer.

    Raises:
        ActionFailedError: If File Explorer cannot be opened.
    """
    try:
        import pywinauto

        if path:
            logger.info("Opening File Explorer at %r", path)
            subprocess.Popen(["explorer.exe", path])
        else:
            logger.info("Opening File Explorer")
            subprocess.Popen(["explorer.exe"])

        deadline = time.monotonic() + _WINDOW_TIMEOUT
        while time.monotonic() < deadline:
            try:
                app = pywinauto.Application(backend="uia")
                # File Explorer window title varies by location (e.g. "C:\", "Documents", etc.)
                app.connect(class_name="CabinetWClass", timeout=2.0)
                logger.debug("Connected to File Explorer")
                return app
            except Exception:
                time.sleep(0.4)

        raise ActionFailedError(
            action="open",
            reason=f"File Explorer window did not appear within {_WINDOW_TIMEOUT}s",
            retryable=True,
        )

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="open_file_explorer",
            reason=f"Failed to open File Explorer: {exc}",
            retryable=True,
        ) from exc


def navigate(app: Any, path: str, config: Config) -> bool:
    """Navigate to a folder path using the address bar.

    Clicking in the address bar and typing the path is the fastest and most
    reliable navigation method — much faster than clicking through folders.

    Args:
        app: pywinauto.Application connected to File Explorer.
        path: Target path (e.g. "C:\\Users\\Documents").
        config: WindowsAgent configuration.

    Returns:
        True if navigation succeeded.

    Raises:
        ActionFailedError: If navigation fails.
    """
    try:
        from windowsagent.actor.input_actor import hotkey, press_key, type_text

        main_win = app.top_window()
        main_win.set_focus()
        time.sleep(0.1)

        # Alt+D focuses the address bar in File Explorer
        hotkey("alt", "d")
        time.sleep(0.2)

        # Select all and type the new path
        hotkey("ctrl", "a")
        time.sleep(0.05)
        type_text(path)
        time.sleep(0.1)
        press_key("enter")
        time.sleep(0.5)  # Wait for navigation to complete

        logger.debug("Navigated File Explorer to %r", path)
        return True

    except Exception as exc:
        raise ActionFailedError(
            action="navigate",
            reason=f"Navigation to {path!r} failed: {exc}",
            retryable=True,
        ) from exc


def list_items(app: Any, config: Config) -> list[str]:
    """Return the names of all currently visible files and folders.

    Args:
        app: pywinauto.Application connected to File Explorer.
        config: WindowsAgent configuration.

    Returns:
        List of item names in the current folder view.
    """
    try:
        from windowsagent.observer.uia import get_tree

        tree = get_tree(app, force_refresh=True)

        items: list[str] = []

        def _collect_list_items(element: UIAElement) -> None:
            if element.control_type in ("ListItem", "DataItem"):
                if element.name and element.name not in items:
                    items.append(element.name)
            for child in element.children:
                _collect_list_items(child)

        _collect_list_items(tree.root)
        logger.debug("Listed %d items in File Explorer", len(items))
        return items

    except Exception as exc:
        raise ActionFailedError(
            action="list_items",
            reason=f"Could not list folder contents: {exc}",
            retryable=True,
        ) from exc


def click_item(app: Any, name: str, config: Config) -> bool:
    """Click (single-click) a file or folder to select it.

    Args:
        app: pywinauto.Application connected to File Explorer.
        name: Exact or partial item name.
        config: WindowsAgent configuration.

    Returns:
        True if click succeeded.
    """
    try:
        from windowsagent.actor.uia_actor import click
        from windowsagent.observer.uia import find_element, get_tree

        tree = get_tree(app)
        element = (
            find_element(tree, name=name, control_type="ListItem")
            or find_element(tree, name=name, control_type="DataItem")
            or find_element(tree, name=name)
        )

        if element is None:
            raise ActionFailedError(
                action="click_item",
                reason=f"Item {name!r} not found in current view",
                retryable=True,
            )

        return click(element, config)

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="click_item",
            reason=f"Click on {name!r} failed: {exc}",
            retryable=True,
        ) from exc


def double_click_item(app: Any, name: str, config: Config) -> bool:
    """Double-click a file or folder to open it.

    Args:
        app: pywinauto.Application connected to File Explorer.
        name: Exact or partial item name.
        config: WindowsAgent configuration.

    Returns:
        True if double-click succeeded.
    """
    try:
        from windowsagent.actor.input_actor import double_click_at
        from windowsagent.observer.uia import find_element, get_tree

        tree = get_tree(app)
        element = (
            find_element(tree, name=name, control_type="ListItem")
            or find_element(tree, name=name, control_type="DataItem")
            or find_element(tree, name=name)
        )

        if element is None:
            raise ActionFailedError(
                action="double_click_item",
                reason=f"Item {name!r} not found in current view",
                retryable=True,
            )

        cx, cy = element.centre
        double_click_at(cx, cy, config=config)
        logger.debug("Double-clicked item %r", name)
        return True

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="double_click_item",
            reason=f"Double-click on {name!r} failed: {exc}",
            retryable=True,
        ) from exc


def create_folder(app: Any, name: str, config: Config) -> bool:
    """Create a new folder in the current directory.

    Uses the keyboard shortcut Ctrl+Shift+N (New Folder) which is available
    in Windows 10 and 11 File Explorer.

    Args:
        app: pywinauto.Application connected to File Explorer.
        name: Name for the new folder.
        config: WindowsAgent configuration.

    Returns:
        True if folder was created.
    """
    try:
        from windowsagent.actor.input_actor import hotkey, press_key, type_text

        main_win = app.top_window()
        main_win.set_focus()
        time.sleep(0.1)

        # Ctrl+Shift+N creates a new folder
        hotkey("ctrl", "shift", "n")
        time.sleep(0.5)  # Wait for rename mode to activate

        # Type the folder name (the new folder starts in rename mode)
        type_text(name)
        time.sleep(0.1)
        press_key("enter")
        time.sleep(0.3)

        logger.debug("Created folder %r", name)
        return True

    except Exception as exc:
        raise ActionFailedError(
            action="create_folder",
            reason=f"Create folder {name!r} failed: {exc}",
            retryable=True,
        ) from exc


def delete_item(app: Any, name: str, config: Config) -> bool:
    """Move a file or folder to the Recycle Bin.

    IMPORTANT: This moves the item to the Recycle Bin. It does NOT permanently
    delete. The user can recover the item from the Recycle Bin.

    Args:
        app: pywinauto.Application connected to File Explorer.
        name: Name of item to delete.
        config: WindowsAgent configuration.

    Returns:
        True if item was moved to Recycle Bin.
    """
    try:
        from windowsagent.actor.input_actor import press_key

        # First select the item
        click_item(app, name, config)
        time.sleep(0.1)

        # Press Delete (moves to Recycle Bin)
        press_key("delete")
        time.sleep(0.3)

        # Handle confirmation dialog if it appears
        try:
            import pywinauto
            confirm = pywinauto.Application(backend="uia")
            confirm.connect(title_re=".*Delete.*|.*Recycle.*", timeout=1.5)
            win = confirm.top_window()
            for btn_name in ("Yes", "OK", "Delete"):
                try:
                    btn = win.child_window(title=btn_name, control_type="Button")
                    btn.click()
                    break
                except Exception:
                    pass
        except Exception:
            pass  # No confirmation dialog — fine

        logger.debug("Moved %r to Recycle Bin", name)
        return True

    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="delete_item",
            reason=f"Delete {name!r} failed: {exc}",
            retryable=True,
        ) from exc


def rename_item(
    app: Any,
    old_name: str,
    new_name: str,
    config: Config,
) -> bool:
    """Rename a file or folder using F2.

    Args:
        app: pywinauto.Application connected to File Explorer.
        old_name: Current name of the item.
        new_name: New name to set.
        config: WindowsAgent configuration.

    Returns:
        True if rename succeeded.
    """
    try:
        from windowsagent.actor.input_actor import hotkey, press_key, type_text

        # Select the item first
        click_item(app, old_name, config)
        time.sleep(0.1)

        # F2 enters rename mode
        press_key("f2")
        time.sleep(0.3)

        # Select all and type new name
        hotkey("ctrl", "a")
        time.sleep(0.05)
        type_text(new_name)
        time.sleep(0.1)
        press_key("enter")
        time.sleep(0.3)

        logger.debug("Renamed %r to %r", old_name, new_name)
        return True

    except Exception as exc:
        raise ActionFailedError(
            action="rename_item",
            reason=f"Rename {old_name!r} -> {new_name!r} failed: {exc}",
            retryable=True,
        ) from exc
