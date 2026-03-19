"""
Element inspector -- search, property display, and profile export.

Provides search filtering over flattened UIA elements and generates
community profile code snippets from selected elements.
"""
from __future__ import annotations

import re
from typing import Any


def search_elements(
    elements: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Filter elements by substring match on name, automation_id, or control_type.

    Args:
        elements: Flat list of UIA element dicts.
        query: Search string (case-insensitive). Empty returns all.

    Returns:
        Filtered list of matching elements.
    """
    if not query:
        return elements

    q = query.lower()
    return [
        e for e in elements
        if q in e.get("name", "").lower()
        or q in e.get("automation_id", "").lower()
        or q in e.get("control_type", "").lower()
    ]


def element_to_profile_entry(element: dict[str, Any]) -> dict[str, Any]:
    """Convert a UIA element dict to a profile known_element entry.

    Returns a dict suitable for inclusion in an app profile's
    known_elements list.
    """
    return {
        "name": element.get("name", ""),
        "control_type": element.get("control_type", ""),
        "automation_id": element.get("automation_id", ""),
        "patterns": element.get("patterns", []),
    }


def generate_profile_snippet(
    app_name: str,
    entries: list[dict[str, Any]],
) -> str:
    """Generate a Python community profile class from selected elements.

    Args:
        app_name: Process name (e.g. "myapp.exe").
        entries: List of profile entries from element_to_profile_entry().

    Returns:
        Python source code string for a BaseAppProfile subclass.
    """
    clean = re.sub(r"[^a-zA-Z0-9]", "", app_name.split(".")[0])
    class_name = clean.capitalize() + "Profile"

    lines = [
        f'"""Auto-generated profile for {app_name}."""',
        "from __future__ import annotations",
        "",
        "from typing import ClassVar",
        "",
        "from windowsagent.apps.base import BaseAppProfile",
        "",
        "",
        f"class {class_name}(BaseAppProfile):",
        f'    """Profile for {app_name}."""',
        "",
        f'    app_names: ClassVar[list[str]] = ["{app_name}"]',
        "    window_titles: ClassVar[list[str]] = []",
        "",
        "    known_elements: ClassVar[list[dict[str, str]]] = [",
    ]

    for entry in entries:
        name = entry.get("name", "")
        ct = entry.get("control_type", "")
        aid = entry.get("automation_id", "")
        lines.append(
            f'        {{"name": "{name}", "control_type": "{ct}", '
            f'"automation_id": "{aid}"}},'
        )

    lines.append("    ]")
    lines.append("")

    return "\n".join(lines)
