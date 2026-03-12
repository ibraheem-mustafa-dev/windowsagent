"""
Tests for the browser grounding module.

Unit tests for VirtualPage and VirtualElement data structures.
Integration test stub for live Chrome CDP testing (requires Chrome running).
"""

from __future__ import annotations

import pytest

from windowsagent.browser.virtual_page import VirtualElement, VirtualPage


def _make_element(
    index: int = 0,
    role: str = "button",
    name: str = "Test",
    tag: str = "button",
    x: int = 100,
    y: int = 200,
    width: int = 80,
    height: int = 32,
    is_visible: bool = True,
    is_interactable: bool = True,
    is_in_viewport: bool = True,
    backend_node_id: int = 1,
    frame_id: str = "",
    **kwargs: object,
) -> VirtualElement:
    """Helper to create a VirtualElement with sensible defaults."""
    return VirtualElement(
        index=index,
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
        **kwargs,
    )


def _make_page(elements: list[VirtualElement] | None = None) -> VirtualPage:
    """Helper to create a VirtualPage with mock data."""
    if elements is None:
        elements = [
            _make_element(index=0, role="button", name="Sign In", x=450, y=120),
            _make_element(
                index=1,
                role="textbox",
                name="Email",
                tag="input",
                x=300,
                y=200,
                value="",
                placeholder="Enter email",
            ),
            _make_element(
                index=2,
                role="link",
                name="Forgot password?",
                tag="a",
                x=310,
                y=260,
                href="/reset",
            ),
            _make_element(
                index=-1,
                role="heading",
                name="Welcome",
                tag="h1",
                x=200,
                y=50,
                is_interactable=False,
            ),
            _make_element(
                index=3,
                role="img",
                name="Map",
                tag="canvas",
                x=0,
                y=400,
                width=800,
                height=600,
                needs_vision_fallback=True,
                is_interactable=False,
            ),
        ]
    return VirtualPage(
        url="https://example.com/login",
        title="Sign In",
        elements=elements,
        scroll_x=0,
        scroll_y=0,
        viewport_width=1440,
        viewport_height=900,
        page_text="Welcome\nSign in to your account",
    )


class TestVirtualPageToLlmPrompt:
    """Tests for VirtualPage.to_llm_prompt()."""

    def test_interactable_only_excludes_non_interactable(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt(interactable_only=True)
        # Should include button, textbox, link
        assert '[0] button "Sign In"' in prompt
        assert '[1] textbox "Email"' in prompt
        assert '[2] link "Forgot password?"' in prompt
        # Should NOT include heading (index=-1)
        assert "heading" not in prompt

    def test_include_all_shows_everything(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt(interactable_only=False)
        assert "heading" in prompt
        assert "Welcome" in prompt

    def test_prompt_header_contains_page_info(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt()
        assert "Sign In" in prompt
        assert "https://example.com/login" in prompt
        assert "1440x900" in prompt

    def test_value_and_placeholder_shown(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt()
        assert 'value=""' in prompt
        assert 'placeholder="Enter email"' in prompt

    def test_href_shown_for_links(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt()
        assert 'href="/reset"' in prompt

    def test_canvas_flagged(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt(interactable_only=False)
        assert "[canvas]" in prompt

    def test_coordinates_in_output(self) -> None:
        page = _make_page()
        prompt = page.to_llm_prompt()
        assert "(450,120)" in prompt
        assert "(300,200)" in prompt

    def test_empty_page(self) -> None:
        page = _make_page(elements=[])
        prompt = page.to_llm_prompt()
        # Should still have the header
        assert "Page:" in prompt
        assert "Viewport:" in prompt


class TestVirtualPageFindByRoleName:
    """Tests for VirtualPage.find_by_role_name()."""

    def test_finds_exact_match(self) -> None:
        page = _make_page()
        el = page.find_by_role_name("button", "Sign In")
        assert el is not None
        assert el.index == 0
        assert el.name == "Sign In"

    def test_finds_partial_match(self) -> None:
        page = _make_page()
        el = page.find_by_role_name("link", "Forgot")
        assert el is not None
        assert el.name == "Forgot password?"

    def test_case_insensitive(self) -> None:
        page = _make_page()
        el = page.find_by_role_name("BUTTON", "sign in")
        assert el is not None
        assert el.role == "button"

    def test_returns_none_when_not_found(self) -> None:
        page = _make_page()
        el = page.find_by_role_name("button", "Nonexistent")
        assert el is None

    def test_returns_none_for_wrong_role(self) -> None:
        page = _make_page()
        el = page.find_by_role_name("textbox", "Sign In")
        assert el is None


class TestVirtualPageFindByIndex:
    """Tests for VirtualPage.find_by_index()."""

    def test_finds_by_index(self) -> None:
        page = _make_page()
        el = page.find_by_index(1)
        assert el is not None
        assert el.role == "textbox"
        assert el.name == "Email"

    def test_returns_none_for_invalid_index(self) -> None:
        page = _make_page()
        el = page.find_by_index(999)
        assert el is None


@pytest.mark.integration
class TestBrowserGroundingIntegration:
    """Integration tests for BrowserGrounding — requires Chrome running with CDP.

    To run these tests manually:
    1. Launch Chrome: chrome.exe --remote-debugging-port=9222 --no-first-run
    2. Navigate to any page
    3. Run: pytest tests/test_browser.py -m integration -v

    These tests are skipped by default in CI/unit test runs.
    """

    @pytest.mark.asyncio
    async def test_capture_virtual_page(self) -> None:
        """Connect to Chrome CDP and capture a VirtualPage."""
        from windowsagent.browser.grounder import BrowserGrounding

        grounder = BrowserGrounding()
        try:
            await grounder.attach_to_existing("http://localhost:9222")
            page = await grounder.capture_virtual_page()

            assert page.url != ""
            assert page.viewport_width > 0
            assert page.viewport_height > 0
            assert len(page.elements) > 0

            # Check LLM prompt generation works
            prompt = page.to_llm_prompt()
            assert "Page:" in prompt
        finally:
            await grounder.close()
