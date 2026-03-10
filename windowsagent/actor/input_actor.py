"""
Input Actor — fallback coordinate-based input via pyautogui.

Used when UIA patterns are not available or fail. All coordinates are in
logical pixels; the module handles DPI scaling before passing to pyautogui.

pyautogui safety:
- FAILSAFE is always enabled (move mouse to top-left corner to abort)
- Mouse movements use a short duration to avoid triggering Windows focus bugs
  that occur with instant (0ms) mouse jumps
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import ActionFailedError

if TYPE_CHECKING:
    from windowsagent.config import Config

logger = logging.getLogger(__name__)

# Short movement duration prevents focus management issues on Windows
_MOVE_DURATION = 0.08  # seconds


def _get_pyautogui() -> Any:
    """Import pyautogui with safety settings applied."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.02  # 20ms between actions
        return pyautogui
    except ImportError as exc:
        raise ActionFailedError(
            action="input",
            reason="pyautogui not installed",
            retryable=False,
        ) from exc


def _scale_coords(x: int, y: int, config: Config | None) -> tuple[int, int]:
    """Convert logical pixel coordinates to physical coordinates for pyautogui.

    pyautogui works in physical pixels on most Windows setups. We scale using
    the primary monitor DPI unless the caller provides a different scale.
    """
    try:
        from windowsagent.observer.screenshot import get_dpi_scale
        scale = get_dpi_scale()
        return int(x * scale), int(y * scale)
    except Exception:
        return x, y


def click_at(
    x: int,
    y: int,
    button: str = "left",
    config: Config | None = None,
) -> bool:
    """Click at logical pixel coordinates.

    Args:
        x: Horizontal position in logical pixels.
        y: Vertical position in logical pixels.
        button: "left", "right", or "middle".
        config: WindowsAgent configuration.

    Returns:
        True on success.

    Raises:
        ActionFailedError: If click fails.
    """
    pyautogui = _get_pyautogui()
    px, py = _scale_coords(x, y, config)

    try:
        pyautogui.click(px, py, button=button, duration=_MOVE_DURATION)
        logger.debug("click_at (%d, %d) [logical] -> (%d, %d) [physical]", x, y, px, py)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="click_at",
            reason=f"Click at ({x}, {y}) failed: {exc}",
            retryable=True,
        ) from exc


def double_click_at(
    x: int,
    y: int,
    config: Config | None = None,
) -> bool:
    """Double-click at logical pixel coordinates.

    Args:
        x: Horizontal position in logical pixels.
        y: Vertical position in logical pixels.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()
    px, py = _scale_coords(x, y, config)

    try:
        pyautogui.doubleClick(px, py, duration=_MOVE_DURATION)
        logger.debug("double_click_at (%d, %d)", x, y)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="double_click_at",
            reason=f"Double-click at ({x}, {y}) failed: {exc}",
            retryable=True,
        ) from exc


def right_click_at(
    x: int,
    y: int,
    config: Config | None = None,
) -> bool:
    """Right-click at logical pixel coordinates.

    Args:
        x: Horizontal position in logical pixels.
        y: Vertical position in logical pixels.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    return click_at(x, y, button="right", config=config)


def type_text(text: str, config: Config | None = None) -> bool:
    """Type text at the current cursor position.

    Uses pyautogui.write() for ASCII characters and pyautogui.typewrite()
    for special characters. For Unicode text, uses clipboard paste.

    Args:
        text: Text to type.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()

    try:
        # For non-ASCII or special characters, use clipboard
        if not text.isascii():
            try:
                import pyautogui as pag

                from windowsagent.actor.clipboard import set_text
                set_text(text)
                pag.hotkey("ctrl", "v")
                logger.debug("Typed %d Unicode chars via clipboard paste", len(text))
                return True
            except Exception as exc:
                logger.debug("Clipboard paste for Unicode failed: %s — trying direct type", exc)

        pyautogui.write(text, interval=0.02)
        logger.debug("Typed %d chars via keyboard simulation", len(text))
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="type_text",
            reason=f"Keyboard typing failed: {exc}",
            retryable=True,
        ) from exc


def press_key(key: str, config: Config | None = None) -> bool:
    """Press a single keyboard key.

    Args:
        key: Key name (pyautogui format: "enter", "escape", "page_down", etc.)
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()

    try:
        pyautogui.press(key)
        logger.debug("Pressed key %r", key)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="press_key",
            reason=f"Key press {key!r} failed: {exc}",
            retryable=True,
        ) from exc


def hotkey(*keys: str, config: Config | None = None) -> bool:
    """Press a keyboard shortcut (multiple keys simultaneously).

    Args:
        *keys: Key names in order (e.g. "ctrl", "a" for Ctrl+A).
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()

    try:
        pyautogui.hotkey(*keys)
        logger.debug("Hotkey %s", "+".join(keys))
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="hotkey",
            reason=f"Hotkey {'+'.join(keys)} failed: {exc}",
            retryable=True,
        ) from exc


def scroll_at(
    x: int,
    y: int,
    direction: str,
    amount: int,
    config: Config | None = None,
) -> bool:
    """Scroll at logical pixel coordinates.

    Args:
        x: Horizontal position in logical pixels.
        y: Vertical position in logical pixels.
        direction: "up" or "down" (left/right via keyboard only).
        amount: Number of scroll 'clicks'.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()
    px, py = _scale_coords(x, y, config)

    try:
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount, x=px, y=py)
        logger.debug("scroll_at (%d, %d) direction=%s amount=%d", x, y, direction, amount)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="scroll_at",
            reason=f"Scroll at ({x}, {y}) failed: {exc}",
            retryable=True,
        ) from exc


def move_to(
    x: int,
    y: int,
    config: Config | None = None,
) -> bool:
    """Move the mouse cursor to logical pixel coordinates without clicking.

    Args:
        x: Horizontal position in logical pixels.
        y: Vertical position in logical pixels.
        config: WindowsAgent configuration.

    Returns:
        True on success.
    """
    pyautogui = _get_pyautogui()
    px, py = _scale_coords(x, y, config)

    try:
        pyautogui.moveTo(px, py, duration=_MOVE_DURATION)
        return True
    except Exception as exc:
        raise ActionFailedError(
            action="move_to",
            reason=f"Mouse move to ({x}, {y}) failed: {exc}",
            retryable=True,
        ) from exc
