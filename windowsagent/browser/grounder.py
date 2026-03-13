"""
Browser grounding via Chrome DevTools Protocol.

Connects to Chrome via playwright.chromium.connect_over_cdp() and extracts
a structured VirtualPage from two CDP calls per step:

1. Accessibility.getFullAXTree — semantic tree (roles, names, states)
2. DOMSnapshot.captureSnapshot with includeDOMRects=true — layout rectangles

Joined by backendDOMNodeId. Produces a flat list of elements with integer
indices for LLM addressing.

Performance: ~50-200ms for both CDP calls combined. No screenshot encoding,
no vision model latency.

Known limitations:
- Canvas/WebGL → needs_vision_fallback=True, use screenshot_element() fallback.
- Closed shadow DOM → invisible to CDP.
- Cross-origin iframes → skipped in v1 (needs Target.attachToTarget).
- backendDOMNodeId invalidated by navigation/React remounts → always re-extract.
- AX tree quality depends on site's ARIA authoring.
"""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from windowsagent.browser.virtual_page import VirtualElement, VirtualPage

logger = logging.getLogger(__name__)

# Roles that indicate an element is interactable by the user
INTERACTABLE_ROLES = {
    "button",
    "link",
    "textbox",
    "combobox",
    "listbox",
    "option",
    "checkbox",
    "radio",
    "menuitem",
    "tab",
    "searchbox",
    "spinbutton",
    "slider",
    "switch",
    "treeitem",
    "columnheader",
    "rowheader",
}

# Maximum characters for page_text extraction
MAX_PAGE_TEXT_LENGTH = 50_000


class BrowserGrounding:
    """Structured browser control via Chrome DevTools Protocol.

    Connects to an existing Chrome instance (launched with --remote-debugging-port)
    and provides:
    - capture_virtual_page() — extract AX tree + layout into VirtualPage
    - click_element() / type_into_element() — act on elements by index
    - navigate() — go to a URL
    - screenshot_element() — screenshot fallback for canvas/WebGL
    - evaluate() — run arbitrary JS

    SPA freshness: re-extract at the start of every step. Never cache
    VirtualPage across steps.

    Usage:
        grounder = BrowserGrounding()
        await grounder.attach_to_existing("http://localhost:9222")
        page = await grounder.capture_virtual_page()
        print(page.to_llm_prompt())
        await grounder.click_element(page.find_by_index(1))
        await grounder.close()
    """

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._cdp_session: Any = None

    @property
    def is_connected(self) -> bool:
        """Whether we have an active CDP connection."""
        return self._browser is not None and self._browser.is_connected()

    @property
    def page(self) -> Page:
        """The active page. Raises if not connected."""
        if self._page is None:
            raise RuntimeError("Not connected — call attach_to_existing() first")
        return self._page

    async def attach_to_existing(self, cdp_url: str = "http://localhost:9222") -> None:
        """Connect to Chrome already running with --remote-debugging-port.

        Args:
            cdp_url: The CDP endpoint URL (e.g. http://localhost:9222).

        Raises:
            RuntimeError: If connection fails.
        """
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            await self._playwright.stop()
            self._playwright = None
            raise RuntimeError(f"Failed to connect to Chrome CDP at {cdp_url}: {exc}") from exc

        # Use the first existing context, or create one
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = await self._browser.new_context()

        # Use the first existing page, or create one
        pages = self._context.pages
        if pages:
            self._page = pages[0]
        else:
            self._page = await self._context.new_page()

        # Create a CDP session for raw protocol calls
        self._cdp_session = await self._page.context.new_cdp_session(self._page)

        logger.info("Connected to Chrome CDP at %s", cdp_url)

    async def capture_virtual_page(self) -> VirtualPage:
        """Extract the current page as a structured VirtualPage.

        Makes two CDP calls:
        1. Accessibility.getFullAXTree — roles, names, states
        2. DOMSnapshot.captureSnapshot — bounding boxes

        Joins by backendDOMNodeId. Returns a flat list of elements with
        integer indices for interactable elements.

        Returns:
            VirtualPage with all visible elements and page metadata.
        """
        page = self.page
        cdp = self._cdp_session

        # Get page metadata
        url = page.url
        title = await page.title()

        # Get viewport dimensions and scroll position
        viewport_info = await page.evaluate(
            """() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                scrollX: window.scrollX,
                scrollY: window.scrollY,
            })"""
        )

        # CDP call 1: Accessibility tree
        ax_tree = await cdp.send("Accessibility.getFullAXTree")
        ax_nodes: list[dict[str, Any]] = ax_tree.get("nodes", [])

        # CDP call 2: DOM snapshot with layout rects
        snapshot = await cdp.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": ["display", "visibility", "opacity"],
                "includeDOMRects": True,
            },
        )

        # Build a map: backendDOMNodeId → bounding rect + tag
        node_rects: dict[int, dict[str, Any]] = {}
        documents = snapshot.get("documents", [])
        for doc in documents:
            nodes = doc.get("nodes", {})
            layout = doc.get("layout", {})
            node_indices = layout.get("nodeIndex", [])
            bounds = layout.get("bounds", [])
            # Get node names (tag names) from the string table
            string_table = snapshot.get("strings", [])
            node_names = nodes.get("nodeName", [])
            backend_node_ids = nodes.get("backendNodeId", [])

            for i, node_idx in enumerate(node_indices):
                if node_idx < len(backend_node_ids) and i < len(bounds):
                    backend_id = backend_node_ids[node_idx]
                    rect = bounds[i]
                    tag = ""
                    if node_idx < len(node_names):
                        name_idx = node_names[node_idx]
                        if name_idx < len(string_table):
                            tag = string_table[name_idx].lower()
                    node_rects[backend_id] = {
                        "x": int(rect[0]) if len(rect) > 0 else 0,
                        "y": int(rect[1]) if len(rect) > 1 else 0,
                        "width": int(rect[2]) if len(rect) > 2 else 0,
                        "height": int(rect[3]) if len(rect) > 3 else 0,
                        "tag": tag,
                    }

        # Build elements from AX tree, enriched with layout
        vp_width = viewport_info["width"]
        vp_height = viewport_info["height"]
        scroll_x = viewport_info["scrollX"]
        scroll_y = viewport_info["scrollY"]

        elements: list[VirtualElement] = []
        interactable_index = 0

        for ax_node in ax_nodes:
            role_data = ax_node.get("role", {})
            role = role_data.get("value", "") if isinstance(role_data, dict) else str(role_data)

            # Skip generic/structural roles
            if role in ("none", "generic", "RootWebArea", "InlineTextBox", ""):
                continue

            name_data = ax_node.get("name", {})
            name = name_data.get("value", "") if isinstance(name_data, dict) else str(name_data)

            # Get backendDOMNodeId from the AX node
            backend_node_id = ax_node.get("backendDOMNodeId", 0)

            # Look up layout rect
            rect_info = node_rects.get(backend_node_id, {})
            x = rect_info.get("x", 0)
            y = rect_info.get("y", 0)
            width = rect_info.get("width", 0)
            height = rect_info.get("height", 0)
            tag = rect_info.get("tag", "")

            # Determine visibility
            is_visible = width > 0 and height > 0
            is_ignored = ax_node.get("ignored", False)
            if is_ignored:
                is_visible = False

            # Determine if in viewport
            el_right = x + width
            el_bottom = y + height
            is_in_viewport = (
                is_visible
                and el_right > scroll_x
                and x < scroll_x + vp_width
                and el_bottom > scroll_y
                and y < scroll_y + vp_height
            )

            # Determine interactability
            role_lower = role.lower()
            is_interactable = role_lower in INTERACTABLE_ROLES and is_visible

            # Canvas fallback detection — catch canvas tags regardless of ARIA role
            # Some apps (e.g. Excalidraw) use role="Canvas" not role="img"
            needs_vision = False
            if tag == "canvas" or role_lower in ("canvas",):
                is_interactable = False
                needs_vision = True

            # Extract optional properties
            props = ax_node.get("properties", [])
            value: str | None = None
            description: str | None = None
            placeholder: str | None = None

            value_data = ax_node.get("value", {})
            if isinstance(value_data, dict) and value_data.get("value"):
                value = str(value_data["value"])

            for prop in props:
                prop_name = prop.get("name", "")
                prop_val = prop.get("value", {})
                prop_value_str = (
                    prop_val.get("value", "") if isinstance(prop_val, dict) else str(prop_val)
                )
                if prop_name == "description" and prop_value_str:
                    description = prop_value_str
                elif prop_name == "placeholder" and prop_value_str:
                    placeholder = prop_value_str

            # Extract href from properties if available
            href: str | None = None
            if role_lower == "link":
                for prop in props:
                    if prop.get("name") == "url":
                        url_val = prop.get("value", {})
                        href = (
                            url_val.get("value", "")
                            if isinstance(url_val, dict)
                            else str(url_val)
                        )
                        break

            # Assign index: interactable elements get sequential indices, others get -1
            if is_interactable:
                idx = interactable_index
                interactable_index += 1
            else:
                idx = -1

            frame_id = ax_node.get("frameId", "")

            elements.append(
                VirtualElement(
                    index=idx,
                    role=role,
                    name=name,
                    tag=tag,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    is_visible=is_visible,
                    is_interactable=is_interactable,
                    is_in_viewport=is_in_viewport,
                    backend_node_id=backend_node_id,
                    frame_id=frame_id,
                    value=value,
                    placeholder=placeholder,
                    description=description,
                    href=href,
                    needs_vision_fallback=needs_vision,
                )
            )

        # Extract page text (capped)
        page_text = await page.evaluate("() => document.body?.innerText || ''")
        if len(page_text) > MAX_PAGE_TEXT_LENGTH:
            page_text = page_text[:MAX_PAGE_TEXT_LENGTH]

        return VirtualPage(
            url=url,
            title=title,
            elements=elements,
            scroll_x=int(scroll_x),
            scroll_y=int(scroll_y),
            viewport_width=int(vp_width),
            viewport_height=int(vp_height),
            page_text=page_text,
        )

    async def click_element(self, element: VirtualElement) -> None:
        """Click an element at its centre coordinates.

        Args:
            element: The VirtualElement to click.
        """
        cx = element.x + element.width // 2
        cy = element.y + element.height // 2
        await self.page.mouse.click(cx, cy)
        logger.debug("Clicked element [%d] %s at (%d, %d)", element.index, element.role, cx, cy)

    async def type_into_element(self, element: VirtualElement, text: str) -> None:
        """Click an element to focus it, then type text.

        Args:
            element: The VirtualElement to type into (should be a textbox/searchbox).
            text: The text to type.
        """
        await self.click_element(element)
        await self.page.keyboard.type(text)
        logger.debug(
            "Typed %d chars into element [%d] %s",
            len(text),
            element.index,
            element.role,
        )

    async def navigate(self, url: str) -> None:
        """Navigate to a URL and wait for network idle.

        Args:
            url: The URL to navigate to.
        """
        await self.page.goto(url, wait_until="networkidle", timeout=30_000)
        logger.info("Navigated to %s", url)

    async def screenshot_element(self, element: VirtualElement) -> bytes:
        """Take a screenshot of an element's bounding box.

        Used as fallback for canvas/WebGL content that can't be read via AX tree.

        Args:
            element: The VirtualElement to screenshot.

        Returns:
            PNG image bytes.
        """
        return await self.page.screenshot(
            clip={
                "x": float(element.x),
                "y": float(element.y),
                "width": float(max(element.width, 1)),
                "height": float(max(element.height, 1)),
            },
            type="png",
        )

    async def screenshot_viewport(self) -> bytes:
        """Take a screenshot of the full viewport.

        Returns:
            PNG image bytes.
        """
        return await self.page.screenshot(type="png")

    async def evaluate(self, js: str) -> Any:
        """Run arbitrary JavaScript in the page context.

        Args:
            js: JavaScript expression or function body to evaluate.

        Returns:
            The result of the JS evaluation.
        """
        return await self.page.evaluate(js)

    async def scroll(self, direction: str = "down", amount: int = 300) -> None:
        """Scroll the page.

        Args:
            direction: "down" or "up".
            amount: Pixels to scroll.
        """
        delta = amount if direction == "down" else -amount
        await self.page.mouse.wheel(0, delta)
        logger.debug("Scrolled %s by %d px", direction, amount)

    async def press_keys(self, keys: str) -> None:
        """Press a keyboard shortcut.

        Args:
            keys: Comma-separated key names (e.g. "ctrl,t" or "Enter").
                  Mapped to Playwright key syntax.
        """
        key_parts = [k.strip() for k in keys.split(",")]

        # Map common names to Playwright key names
        key_map = {
            "ctrl": "Control",
            "alt": "Alt",
            "shift": "Shift",
            "meta": "Meta",
            "enter": "Enter",
            "tab": "Tab",
            "escape": "Escape",
            "backspace": "Backspace",
            "delete": "Delete",
            "space": " ",
        }

        mapped = [key_map.get(k.lower(), k) for k in key_parts]

        if len(mapped) == 1:
            await self.page.keyboard.press(mapped[0])
        else:
            # Hold modifiers, press last key, release modifiers
            modifiers = mapped[:-1]
            final_key = mapped[-1]
            for mod in modifiers:
                await self.page.keyboard.down(mod)
            await self.page.keyboard.press(final_key)
            for mod in reversed(modifiers):
                await self.page.keyboard.up(mod)

        logger.debug("Pressed keys: %s", keys)

    async def close(self) -> None:
        """Close the CDP connection. Does not kill Chrome."""
        if self._cdp_session:
            try:
                await self._cdp_session.detach()
            except Exception:
                pass
            self._cdp_session = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._context = None
        self._page = None
        logger.info("Browser grounding connection closed")
