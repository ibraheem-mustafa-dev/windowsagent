"""
UIA Grounder — match a natural language description to a UIAElement.

The UIA grounder uses the accessibility tree to find the best matching
element for a given description. No API calls are made — this is fast,
deterministic, and free.

Matching algorithm:
1. Extract search criteria from the description (keywords, type hints)
2. Run find_element() with progressively looser criteria
3. Return a GroundedElement with a confidence score
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from windowsagent.observer.uia import UIAElement, UIATree

logger = logging.getLogger(__name__)

# Keywords in descriptions that hint at specific control types
TYPE_HINTS: dict[str, str] = {
    "document": "Document",
    "text area": "Document",
    "textarea": "Document",
    "content": "Document",
    "button": "Button",
    "btn": "Button",
    "click": "Button",
    "press": "Button",
    "text box": "Edit",
    "textbox": "Edit",
    "text field": "Edit",
    "input": "Edit",
    "field": "Edit",
    "edit": "Edit",
    "enter": "Edit",
    "type": "Edit",
    "dropdown": "ComboBox",
    "combo": "ComboBox",
    "select": "ComboBox",
    "list": "List",
    "listbox": "List",
    "checkbox": "CheckBox",
    "check box": "CheckBox",
    "tick": "CheckBox",
    "radio": "RadioButton",
    "menu": "MenuItem",
    "menuitem": "MenuItem",
    "tab": "TabItem",
    "link": "Hyperlink",
    "tree": "TreeItem",
    "slider": "Slider",
    "scroll": "ScrollBar",
}


@dataclass
class GroundedElement:
    """A UI element that has been matched to a natural language description.

    Contains both the UIA reference (for pattern-based actions) and screen
    coordinates (for fallback coordinate-based actions).
    """

    method: Literal["uia", "vision", "ocr"]
    uia_element: UIAElement | None
    coordinates: tuple[int, int]              # Centre point in logical pixels
    confidence: float                          # 0.0-1.0
    bounding_rect: tuple[int, int, int, int]  # (left, top, right, bottom)
    description_matched: str                   # The description that produced this match


def ground(
    description: str,
    tree: UIATree,
    context: str | None = None,
) -> GroundedElement | None:
    """Match a natural language description to the best UIAElement in the tree.

    Args:
        description: Natural language description (e.g. "the Send button",
                     "Subject field", "email list").
        tree: UIATree to search.
        context: Optional additional context (e.g. current app name).

    Returns:
        GroundedElement with confidence score, or None if no match found.
    """
    from windowsagent.observer.uia import find_element

    clean_desc = _clean_description(description)
    keywords = _extract_keywords(clean_desc)
    type_hint = _extract_type_hint(clean_desc)
    automation_id_hint = _extract_automation_id(clean_desc)

    logger.debug(
        "UIA grounding: description=%r keywords=%r type=%r id=%r",
        description,
        keywords,
        type_hint,
        automation_id_hint,
    )

    # Attempt 1: automation_id exact match (highest confidence)
    if automation_id_hint:
        element = find_element(tree, automation_id=automation_id_hint)
        if element:
            return _make_grounded(element, description, confidence=0.98)

    # Attempt 2: exact keyword + type match
    if keywords and type_hint:
        element = find_element(tree, name=keywords[0], control_type=type_hint)
        if element:
            return _make_grounded(element, description, confidence=0.92)

    # Attempt 3: first keyword with type hint (looser)
    if keywords:
        for keyword in keywords:
            element = find_element(tree, name=keyword, control_type=type_hint)
            if element:
                return _make_grounded(element, description, confidence=0.85)

    # Attempt 4: multi-keyword search (join keywords and search as phrase)
    if len(keywords) > 1:
        phrase = " ".join(keywords)
        element = find_element(tree, name=phrase)
        if element:
            return _make_grounded(element, description, confidence=0.80)

    # Attempt 5: each keyword individually
    for keyword in keywords:
        element = find_element(tree, name=keyword)
        if element:
            return _make_grounded(element, description, confidence=0.70)

    # Attempt 6: type-only match (last resort)
    if type_hint:
        element = find_element(tree, control_type=type_hint)
        if element:
            return _make_grounded(element, description, confidence=0.50)

    logger.debug("UIA grounding found no match for %r", description)
    return None


# ── Private helpers ──────────────────────────────────────────────────────────


def _clean_description(description: str) -> str:
    """Remove filler words and normalise the description for matching."""
    filler = (
        r"\b(the|a|an|this|that|my|please|click|tap|press|on|in|at|to|of|"
        r"button|field|box|control|element|area|panel|dialog|window)\b"
    )
    cleaned = re.sub(filler, " ", description.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_keywords(description: str) -> list[str]:
    """Extract meaningful keywords from a cleaned description."""
    # Split into words, filter short stop words
    words = description.split()
    keywords = [w for w in words if len(w) > 2]
    return keywords[:3]  # Top 3 keywords are enough


def _extract_type_hint(description: str) -> str | None:
    """Extract a control type hint from the description."""
    for keyword, ctrl_type in TYPE_HINTS.items():
        if keyword in description:
            return ctrl_type
    return None


def _extract_automation_id(description: str) -> str | None:
    """Extract an explicit automation ID from the description.

    Descriptions of the form "automation_id:SomeId" are treated as
    explicit automation ID lookups.
    """
    match = re.search(r"automation_id[:\s]+(\w+)", description, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _make_grounded(
    element: UIAElement,
    description: str,
    confidence: float,
) -> GroundedElement:
    """Create a GroundedElement from a UIAElement match."""
    return GroundedElement(
        method="uia",
        uia_element=element,
        coordinates=element.centre,
        confidence=confidence,
        bounding_rect=element.rect,
        description_matched=description,
    )
