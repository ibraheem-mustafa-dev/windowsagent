"""
UIA Actor — executes actions via Windows UI Automation patterns.

This is the primary action execution path. UIA patterns are more reliable than
coordinate-based input because they:
- Trigger the element's semantic action (not just a pixel click)
- Work even if the element is partially obscured
- Don't depend on screen DPI or window position
- Are faster (no mouse movement, no visual feedback required)

Fallback to input_actor.py when UIA patterns are not available.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import (
    ActionFailedError,
    ElementDisabledError,
    ElementNotVisibleError,
)

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import UIAElement

logger = logging.getLogger(__name__)

# Scroll direction constants
SCROLL_DIRECTIONS = frozenset(["up", "down", "left", "right"])


def _require_enabled_visible(element: UIAElement) -> None:
    """Raise appropriate error if element cannot be interacted with."""
    if not element.is_enabled:
        raise ElementDisabledError(element.name or element.control_type)
    if not element.is_visible:
        raise ElementNotVisibleError(element.name or element.control_type)


def _get_wrapper(element: UIAElement) -> Any:
    """Get a fresh pywinauto wrapper for the element using its HWND."""
    try:
        import pywinauto
        if element.hwnd:
            return pywinauto.Desktop(backend="uia").window(handle=element.hwnd)
    except Exception:
        pass
    return None


def focus(element: UIAElement, config: Config) -> bool:
    """Set keyboard focus to an element.

    Attempts to set focus via pywinauto's set_focus() method, which uses
    the UIA SetFocus operation.

    Args:
        element: Target element.
        config: Configuration (unused currently; reserved for timeout).

    Returns:
        True if focus was set successfully.

    Raises:
        ActionFailedError: If focus cannot be set.
    """
    _require_enabled_visible(element)

    try:
        wrapper = _get_wrapper(element)
        if wrapper is not None:
            wrapper.set_focus()
            logger.debug("Focus set via HWND on %r", element.name)
            return True
    except Exception as exc:
        logger.debug("HWND-based focus failed: %s", exc)

    # Fallback: click at centre
    try:
        from windowsagent.actor.input_actor import click_at
        cx, cy = element.centre
        click_at(cx, cy, config=config)
        logger.debug("Focus set via coordinate click on %r", element.name)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="focus",
            reason=f"Could not set focus: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def click(element: UIAElement, config: Config) -> bool:
    """Click an element using InvokePattern if available, else coordinate click.

    InvokePattern is preferred because it triggers the element's semantic
    'invoke' action without requiring the element to be visually accessible.

    Args:
        element: Target element.
        config: WindowsAgent configuration.

    Returns:
        True if click succeeded.

    Raises:
        ElementDisabledError: If element is disabled.
        ElementNotVisibleError: If element is not visible.
        ActionFailedError: If click fails after retries.
    """
    _require_enabled_visible(element)

    # Try InvokePattern first
    if "invoke" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                wrapper.invoke()
                logger.debug("Clicked %r via InvokePattern", element.name)
                return True
        except Exception as exc:
            logger.debug("InvokePattern failed for %r: %s — trying coordinate click", element.name, exc)

    # Fall back to coordinate click
    try:
        from windowsagent.actor.input_actor import click_at
        cx, cy = element.centre
        if cx == 0 and cy == 0:
            raise ActionFailedError(
                action="click",
                reason="Element has zero-size bounding rect",
                retryable=False,
                element_name=element.name,
            )
        click_at(cx, cy, config=config)
        logger.debug("Clicked %r via coordinate click at (%d, %d)", element.name, cx, cy)
        return True
    except ActionFailedError:
        raise
    except Exception as exc:
        raise ActionFailedError(
            action="click",
            reason=f"Both InvokePattern and coordinate click failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def type_text(element: UIAElement, text: str, config: Config) -> bool:
    """Type text into an element using ValuePattern.SetValue or keyboard simulation.

    ValuePattern.SetValue is strongly preferred because it is atomic and does
    not depend on the element having keyboard focus.

    For large text (>100 characters), clipboard paste is used automatically
    for speed.

    Args:
        element: Target edit/text element.
        text: Text to enter.
        config: WindowsAgent configuration.

    Returns:
        True if text was entered successfully.

    Raises:
        ElementDisabledError: If element is disabled.
        ActionFailedError: If text entry fails.
    """
    _require_enabled_visible(element)

    # Special handling for Document elements (like Notepad text area)
    # They don't have ValuePattern, so we use pyautogui directly
    if element.control_type == "Document":
        try:
            from windowsagent.actor.input_actor import click_at
            from windowsagent.actor.input_actor import type_text as _kb_type
            cx, cy = element.centre
            click_at(cx, cy, config=config)
            time.sleep(0.1)
            _kb_type(text, config=config)
            logger.debug("Typed %d chars into Document %r via pyautogui", len(text), element.name)
            return True
        except Exception as exc:
            raise ActionFailedError(
                action="type",
                reason=f"Document typing failed: {exc}",
                retryable=True,
                element_name=element.name,
            ) from exc

    # For large text, use clipboard for speed
    if len(text) > 100 and "value" in element.patterns:
        try:
            from windowsagent.actor.clipboard import paste_to_element
            return paste_to_element(element, text, config)
        except Exception as exc:
            logger.debug("Clipboard paste failed: %s — trying ValuePattern", exc)

    # Try ValuePattern.SetValue
    if "value" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                wrapper.set_edit_text(text)
                logger.debug("Typed %d chars into %r via ValuePattern", len(text), element.name)
                return True
        except Exception as exc:
            logger.debug("ValuePattern.SetValue failed for %r: %s", element.name, exc)

    # Fall back to focus + keyboard typing
    try:
        focus(element, config)
        from windowsagent.actor.input_actor import click_at
        from windowsagent.actor.input_actor import type_text as _kb_type
        cx, cy = element.centre
        click_at(cx, cy, config=config)
        time.sleep(0.05)
        _kb_type(text, config=config)
        logger.debug("Typed %d chars into %r via keyboard simulation", len(text), element.name)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="type",
            reason=f"Text input failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def select(element: UIAElement, config: Config) -> bool:
    """Select an item using SelectionItemPattern.

    Used for list items, radio buttons, combo box items, and tree items.

    Args:
        element: Target element to select.
        config: WindowsAgent configuration.

    Returns:
        True if selection succeeded.

    Raises:
        ElementDisabledError: If element is disabled.
        ActionFailedError: If selection fails.
    """
    _require_enabled_visible(element)

    # Try SelectionItemPattern
    if "selection_item" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                wrapper.select()
                logger.debug("Selected %r via SelectionItemPattern", element.name)
                return True
        except Exception as exc:
            logger.debug("SelectionItemPattern failed for %r: %s", element.name, exc)

    # Fall back to click
    try:
        return click(element, config)
    except Exception as exc:
        raise ActionFailedError(
            action="select",
            reason=f"Selection failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def scroll(
    element: UIAElement,
    direction: str,
    amount: int,
    config: Config,
) -> bool:
    """Scroll an element using ScrollPattern, with keyboard fallback.

    Args:
        element: Target scrollable element.
        direction: One of "up", "down", "left", "right".
        amount: Number of scroll units.
        config: WindowsAgent configuration.

    Returns:
        True if scroll succeeded.

    Raises:
        ActionFailedError: If scroll fails.
    """
    if direction not in SCROLL_DIRECTIONS:
        raise ActionFailedError(
            action="scroll",
            reason=f"Invalid direction {direction!r}. Must be one of: {', '.join(SCROLL_DIRECTIONS)}",
            retryable=False,
            element_name=element.name,
        )

    # Try ScrollPattern
    if "scroll" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                # pywinauto scroll: positive = down/right, negative = up/left
                if direction in ("down", "right"):
                    wrapper.scroll(direction, "line", amount)
                else:
                    wrapper.scroll(direction, "line", amount)
                logger.debug("Scrolled %r %s %d via ScrollPattern", element.name, direction, amount)
                return True
        except Exception as exc:
            logger.debug("ScrollPattern failed for %r: %s", element.name, exc)

    # Fall back to keyboard scroll
    try:
        focus(element, config)
        from windowsagent.actor.input_actor import press_key

        key_map = {
            "up": "page_up" if amount > 1 else "up",
            "down": "page_down" if amount > 1 else "down",
            "left": "left",
            "right": "right",
        }
        key = key_map[direction]
        for _ in range(amount):
            press_key(key, config=config)
            time.sleep(0.05)
        logger.debug("Scrolled %r %s %d via keyboard", element.name, direction, amount)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="scroll",
            reason=f"Scroll failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def expand(element: UIAElement, config: Config) -> bool:
    """Expand a collapsible element using ExpandCollapsePattern.

    Used for tree nodes, combo boxes, menus, and accordions.

    Args:
        element: Target collapsible element.
        config: WindowsAgent configuration.

    Returns:
        True if expand succeeded.

    Raises:
        ElementDisabledError: If element is disabled.
        ActionFailedError: If expand fails.
    """
    _require_enabled_visible(element)

    if "expand_collapse" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                wrapper.expand()
                logger.debug("Expanded %r via ExpandCollapsePattern", element.name)
                return True
        except Exception as exc:
            logger.debug("ExpandCollapsePattern failed for %r: %s", element.name, exc)

    # Fall back to click
    try:
        return click(element, config)
    except Exception as exc:
        raise ActionFailedError(
            action="expand",
            reason=f"Expand failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc


def toggle(element: UIAElement, config: Config) -> bool:
    """Toggle a toggleable element (checkbox, toggle switch) using TogglePattern.

    Args:
        element: Target toggleable element.
        config: WindowsAgent configuration.

    Returns:
        True if toggle succeeded.

    Raises:
        ElementDisabledError: If element is disabled.
        ActionFailedError: If toggle fails.
    """
    _require_enabled_visible(element)

    if "toggle" in element.patterns:
        try:
            wrapper = _get_wrapper(element)
            if wrapper is not None:
                wrapper.toggle()
                logger.debug("Toggled %r via TogglePattern", element.name)
                return True
        except Exception as exc:
            logger.debug("TogglePattern failed for %r: %s", element.name, exc)

    # Fall back to click (works for most checkbox implementations)
    try:
        return click(element, config)
    except Exception as exc:
        raise ActionFailedError(
            action="toggle",
            reason=f"Toggle failed: {exc}",
            retryable=True,
            element_name=element.name,
        ) from exc
