"""
Internal UIA tree building and search helpers.

These functions are implementation details used by uia.py.
External code should use find_element() imported from windowsagent.observer.uia.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from windowsagent.observer.uia_types import PATTERN_NAMES, UIAElement

logger = logging.getLogger(__name__)


def _build_element(wrapper: Any, depth: int, max_depth: int) -> UIAElement:
    """Recursively build a UIAElement from a pywinauto wrapper."""
    try:
        name = wrapper.window_text() or ""
    except Exception:
        name = ""

    try:
        ctrl_type = wrapper.element_info.control_type or "Unknown"
        # pywinauto returns integer or string; normalise to string
        if not isinstance(ctrl_type, str):
            ctrl_type = str(ctrl_type)
    except Exception:
        ctrl_type = "Unknown"

    try:
        automation_id = wrapper.element_info.automation_id or ""
    except Exception:
        automation_id = ""

    try:
        class_name = wrapper.element_info.class_name or ""
    except Exception:
        class_name = ""

    try:
        rect_obj = wrapper.rectangle()
        rect = (rect_obj.left, rect_obj.top, rect_obj.right, rect_obj.bottom)
    except Exception:
        rect = (0, 0, 0, 0)

    try:
        is_enabled = wrapper.is_enabled()
    except Exception:
        is_enabled = False

    try:
        is_visible = wrapper.is_visible()
    except Exception:
        is_visible = False

    try:
        hwnd = wrapper.handle
    except Exception:
        hwnd = 0

    # Detect available patterns
    patterns: list[str] = []
    try:
        for pattern_name, short_name in PATTERN_NAMES.items():
            try:
                if hasattr(wrapper, pattern_name.lower().replace("pattern", "")):
                    patterns.append(short_name)
            except Exception:
                pass
        # Also check via element_info patterns if available
        if hasattr(wrapper, "element_info") and hasattr(wrapper.element_info, "patterns"):
            for p in wrapper.element_info.patterns:
                p_short = PATTERN_NAMES.get(p, p.lower().replace("pattern", ""))
                if p_short not in patterns:
                    patterns.append(p_short)
    except Exception:
        pass

    # Read current value
    value = ""
    try:
        value = wrapper.legacy_properties().get("Value", "") or ""
    except Exception:
        pass
    if not value:
        try:
            value = wrapper.get_value() or ""
        except Exception:
            pass

    # Build children
    children: list[UIAElement] = []
    if depth < max_depth:
        try:
            for child in wrapper.children():
                try:
                    child_elem = _build_element(child, depth + 1, max_depth)
                    children.append(child_elem)
                except Exception as exc:
                    logger.debug("Skipping child element at depth %d: %s", depth + 1, exc)
        except Exception as exc:
            logger.debug("Could not get children at depth %d: %s", depth, exc)

    return UIAElement(
        name=name,
        control_type=ctrl_type,
        automation_id=automation_id,
        class_name=class_name,
        rect=rect,
        is_enabled=is_enabled,
        is_visible=is_visible,
        patterns=patterns,
        value=value,
        children=children,
        depth=depth,
        hwnd=hwnd,
    )


def _search_tree(
    element: UIAElement,
    predicate: Callable[[UIAElement], bool],
) -> UIAElement | None:
    """Depth-first search of the UIA tree using a predicate function."""
    try:
        if predicate(element):
            return element
    except Exception:
        pass

    for child in element.children:
        result = _search_tree(child, predicate)
        if result:
            return result

    return None


def _count_elements(element: UIAElement) -> int:
    """Count total elements in a UIAElement subtree."""
    return 1 + sum(_count_elements(c) for c in element.children)


def find_element(
    tree: Any,
    name: str | None = None,
    control_type: str | None = None,
    automation_id: str | None = None,
    value: str | None = None,
) -> UIAElement | None:
    """Find the best matching element in a UIA tree.

    Matching algorithm (stops at first match, in order of precision):
    1. Exact automation_id match
    2. Exact name + exact control_type match
    3. Case-insensitive name + control_type match
    4. Partial name match (search term contained in element name)
    5. Value match (search term contained in element.value)

    Args:
        tree: The UIATree to search.
        name: Element name to search for.
        control_type: Element control type (e.g. "Button", "Edit").
        automation_id: Automation ID string.
        value: Value/text to match.

    Returns:
        Best matching UIAElement, or None if not found.
    """
    if not any([name, control_type, automation_id, value]):
        return None

    # Normalise search terms
    name_lower: str = name.lower() if name else ""
    type_lower: str = control_type.lower() if control_type else ""

    # Pass 1: exact automation_id
    if automation_id:
        result = _search_tree(
            tree.root,
            lambda e: e.automation_id == automation_id,
        )
        if result:
            return result

    # Pass 2: exact name + exact type
    if name and control_type:
        result = _search_tree(
            tree.root,
            lambda e: (
                e.name == name
                and e.control_type.lower() == type_lower
            ),
        )
        if result:
            return result

    # Pass 3: case-insensitive name + type
    if name and control_type:
        result = _search_tree(
            tree.root,
            lambda e: (
                e.name.lower() == name_lower
                and e.control_type.lower() == type_lower
            ),
        )
        if result:
            return result

    # Pass 4: exact name only (case-insensitive)
    if name:
        result = _search_tree(
            tree.root,
            lambda e: e.name.lower() == name_lower,
        )
        if result:
            return result

    # Pass 5: partial name match
    if name:
        result = _search_tree(
            tree.root,
            lambda e: name_lower in e.name.lower(),
        )
        if result:
            return result

    # Pass 6: control_type only
    if control_type and not name:
        result = _search_tree(
            tree.root,
            lambda e: e.control_type.lower() == type_lower,
        )
        if result:
            return result

    # Pass 7: value match
    if value:
        value_lower = value.lower()
        result = _search_tree(
            tree.root,
            lambda e: value_lower in e.value.lower(),
        )
        if result:
            return result

    return None
