"""
Action execution helpers for the WindowsAgent Agent class.

These are extracted from agent.py to keep agent.py under the 250-line limit.
They are not part of the public API — import Agent from windowsagent.agent instead.

Each function accepts `config` explicitly rather than via `self` so they can
be module-level (not bound methods), enabling easier unit testing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from windowsagent.exceptions import ActionFailedError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.grounder.uia_grounder import GroundedElement
    from windowsagent.observer.state import AppState
    from windowsagent.observer.uia import UIAElement

logger = logging.getLogger(__name__)


def execute_action(
    action: str,
    grounded: GroundedElement | None,
    element: UIAElement | None,
    params: dict[str, Any],
    state: AppState,
    config: Config,
    profile: Any | None = None,
) -> bool:
    """Dispatch to the appropriate actor based on action type and profile strategy."""
    from windowsagent.actor import input_actor, uia_actor

    if action == "click":
        if element:
            return uia_actor.click(element, config)
        if grounded:
            return input_actor.click_at(*grounded.coordinates, config=config)
        return False

    elif action == "type":
        text = str(params.get("text", ""))
        if not text:
            raise ActionFailedError(action="type", reason="No 'text' param provided")
        return execute_type(text, element, grounded, state, config, profile)

    elif action == "scroll":
        direction = str(params.get("direction", "down"))
        amount = int(params.get("amount", 3))
        return execute_scroll(direction, amount, element, grounded, state, config, profile)

    elif action == "key":
        keys = params.get("keys") or [params.get("key", "")]
        if isinstance(keys, str):
            keys = [keys]
        if len(keys) == 1:
            return input_actor.press_key(keys[0], config=config)
        return input_actor.hotkey(*keys, config=config)

    elif action == "expand":
        if element:
            return uia_actor.expand(element, config)
        return False

    elif action == "toggle":
        if element:
            return uia_actor.toggle(element, config)
        return False

    elif action == "select":
        if element:
            return uia_actor.select(element, config)
        return False

    elif action in ("activate", "minimise", "minimize", "maximise", "maximize", "restore"):
        from windowsagent import window_manager
        normalised = action.replace("minimize", "minimise").replace("maximize", "maximise")
        fn_map = {
            "activate": window_manager.activate,
            "minimise": window_manager.minimise,
            "maximise": window_manager.maximise,
            "restore": window_manager.restore,
        }
        fn = fn_map.get(normalised)
        if fn is None:
            return False
        return fn(state.window_title)

    else:
        raise ActionFailedError(
            action=action,
            reason=f"Unknown action type {action!r}. "
            "Supported: click, type, scroll, key, expand, toggle, select, "
            "activate, minimise, maximise, restore",
            retryable=False,
        )


def execute_type(
    text: str,
    element: UIAElement | None,
    grounded: GroundedElement | None,
    state: AppState,
    config: Config,
    profile: Any | None,
) -> bool:
    """Execute a type action, respecting the profile's text input strategy."""
    from windowsagent.actor import input_actor, uia_actor

    strategy = profile.get_text_input_strategy() if profile else "value_pattern"

    if strategy == "clipboard" and element:
        # Profile says always use clipboard (Chrome, Edge, Teams, WebView2)
        from windowsagent.actor.clipboard import paste_to_element
        return paste_to_element(element, text, config)

    if element:
        return uia_actor.type_text(element, text, config, window_hwnd=state.hwnd)

    if grounded:
        input_actor.click_at(*grounded.coordinates, config=config)
        if strategy == "clipboard":
            from windowsagent.actor.clipboard import set_text
            set_text(text)
            return input_actor.hotkey("ctrl", "v", config=config)
        return input_actor.type_text(text, config=config)

    return False


def execute_scroll(
    direction: str,
    amount: int,
    element: UIAElement | None,
    grounded: GroundedElement | None,
    state: AppState,
    config: Config,
    profile: Any | None,
) -> bool:
    """Execute a scroll action, respecting the profile's scroll strategy."""
    from windowsagent.actor import input_actor, uia_actor

    strategy = profile.get_scroll_strategy() if profile else "scroll_pattern"

    if strategy == "webview2":
        # WebView2 apps: mouse wheel doesn't reach inner content.
        # Click in content area + send Page Down/Up keys.
        from windowsagent.observer.uia import get_window
        try:
            window = get_window(hwnd=state.hwnd)
            from windowsagent.apps.webview2 import scroll_content
            return scroll_content(window, direction, amount, config)
        except Exception as exc:
            logger.debug("WebView2 scroll failed, falling back to keyboard: %s", exc)
            key = "page_down" if direction == "down" else "page_up"
            for _ in range(amount):
                input_actor.press_key(key, config=config)
            return True

    if strategy == "keyboard":
        key = "page_down" if direction == "down" else "page_up"
        for _ in range(amount):
            input_actor.press_key(key, config=config)
        return True

    # Default: UIA ScrollPattern or coordinate-based
    if element:
        return uia_actor.scroll(element, direction, amount, config)
    if grounded:
        return input_actor.scroll_at(
            *grounded.coordinates, direction=direction, amount=amount, config=config,
        )
    return False
