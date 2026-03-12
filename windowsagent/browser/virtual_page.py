"""
Virtual page representation for browser grounding.

VirtualElement and VirtualPage are the core data structures that represent
a browser page as a flat list of elements with roles, names, bounding boxes,
and integer indices for LLM addressing.

Built from two CDP calls per step:
- Accessibility.getFullAXTree — semantic tree (roles, names, states)
- DOMSnapshot.captureSnapshot with includeDOMRects=true — layout rectangles

Joined by backendDOMNodeId. Re-extracted every step (never cached).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VirtualElement:
    """A single interactable or visible element on the page.

    Attributes:
        index: Sequential integer for LLM addressing. -1 = not interactable.
        role: ARIA role (e.g. "button", "textbox", "link").
        name: Accessible name from the AX tree.
        tag: HTML tag (best-effort, "" if unknown).
        x: Left edge in CSS pixels.
        y: Top edge in CSS pixels.
        width: Width in CSS pixels.
        height: Height in CSS pixels.
        is_visible: Element has non-zero dimensions and is not aria-hidden.
        is_interactable: Element has an interactable ARIA role.
        is_in_viewport: Element overlaps the current viewport.
        backend_node_id: CDP backendDOMNodeId (invalidated by navigation/remounts).
        frame_id: CDP frame ID this element belongs to.
        value: Current value (for inputs, selects, etc.).
        placeholder: Placeholder text (for inputs).
        description: ARIA description or title attribute.
        href: Link URL (for anchors).
        needs_vision_fallback: True for canvas/WebGL elements that need screenshot.
    """

    index: int
    role: str
    name: str
    tag: str
    x: int
    y: int
    width: int
    height: int
    is_visible: bool
    is_interactable: bool
    is_in_viewport: bool
    backend_node_id: int
    frame_id: str
    value: str | None = None
    placeholder: str | None = None
    description: str | None = None
    href: str | None = None
    needs_vision_fallback: bool = False


@dataclass
class VirtualPage:
    """Structured representation of a browser page for LLM consumption.

    Built from the browser's AX tree + DOM layout. Each element has an integer
    index that the LLM can reference in action commands (e.g. "click element 3").

    Attributes:
        url: Current page URL.
        title: Page title.
        elements: Flat list of all elements (interactable and non-interactable).
        scroll_x: Horizontal scroll offset in CSS pixels.
        scroll_y: Vertical scroll offset in CSS pixels.
        viewport_width: Viewport width in CSS pixels.
        viewport_height: Viewport height in CSS pixels.
        page_text: Full visible text content, capped at 50k characters.
    """

    url: str
    title: str
    elements: list[VirtualElement] = field(default_factory=list)
    scroll_x: int = 0
    scroll_y: int = 0
    viewport_width: int = 0
    viewport_height: int = 0
    page_text: str = ""

    def to_llm_prompt(self, interactable_only: bool = True) -> str:
        """Produce compact text for LLM consumption.

        Format: [index] role "name" (x,y) {extras}

        Args:
            interactable_only: If True, only include elements with index >= 0.

        Returns:
            Multi-line string, one element per line. Example:
                Page: Sign In — https://example.com/login
                Viewport: 1440x900, scroll: (0, 320)
                [1] button "Sign In" (450,120)
                [2] textbox "Email" (300,200) value=""
                [3] link "Forgot password?" (310,260) href="/reset"
        """
        lines: list[str] = [
            f"Page: {self.title} — {self.url}",
            f"Viewport: {self.viewport_width}x{self.viewport_height}, "
            f"scroll: ({self.scroll_x}, {self.scroll_y})",
            "",
        ]

        for el in self.elements:
            if interactable_only and el.index < 0:
                continue

            parts = [f"[{el.index}]", el.role, f'"{el.name}"', f"({el.x},{el.y})"]

            # Add useful extras
            if el.value is not None:
                parts.append(f'value="{el.value}"')
            if el.placeholder:
                parts.append(f'placeholder="{el.placeholder}"')
            if el.href:
                parts.append(f'href="{el.href}"')
            if el.needs_vision_fallback:
                parts.append("[canvas]")

            lines.append(" ".join(parts))

        return "\n".join(lines)

    def find_by_role_name(
        self, role: str, name_fragment: str
    ) -> VirtualElement | None:
        """Case-insensitive search by role + partial name match.

        Args:
            role: ARIA role to match (case-insensitive).
            name_fragment: Substring to match against element name (case-insensitive).

        Returns:
            First matching VirtualElement, or None if not found.
        """
        role_lower = role.lower()
        name_lower = name_fragment.lower()

        for el in self.elements:
            if el.role.lower() == role_lower and name_lower in el.name.lower():
                return el

        return None

    def find_by_index(self, index: int) -> VirtualElement | None:
        """Find an element by its LLM-addressable index.

        Args:
            index: The element index to find.

        Returns:
            The matching VirtualElement, or None if not found.
        """
        for el in self.elements:
            if el.index == index:
                return el
        return None
