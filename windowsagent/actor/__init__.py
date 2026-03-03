"""
Actor module — executes actions on Windows UI elements.

Components:
- uia_actor.py: Execute via UIA patterns (InvokePattern, ValuePattern, etc.)
- input_actor.py: Fallback coordinate-based input via pyautogui
- clipboard.py: Efficient large-text transfer via Win32 clipboard
"""

from windowsagent.actor.clipboard import clear, get_text, paste_to_element, set_text
from windowsagent.actor.input_actor import (
    click_at,
    double_click_at,
    hotkey,
    press_key,
    right_click_at,
    scroll_at,
    type_text as type_at_cursor,
)
from windowsagent.actor.uia_actor import click, expand, focus, scroll, select, toggle, type_text

__all__ = [
    "clear",
    "click",
    "click_at",
    "double_click_at",
    "expand",
    "focus",
    "get_text",
    "hotkey",
    "paste_to_element",
    "press_key",
    "right_click_at",
    "scroll",
    "scroll_at",
    "select",
    "set_text",
    "toggle",
    "type_at_cursor",
    "type_text",
]
