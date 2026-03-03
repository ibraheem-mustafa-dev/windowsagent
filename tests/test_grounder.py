"""
Tests for the grounder module.

All tests here are unit tests using mock/constructed UIA trees.
No real Windows apps are required.
"""

from __future__ import annotations

import time

import pytest


def _make_test_tree() -> "object":
    """Build a realistic UIATree for testing grounding logic."""
    from windowsagent.observer.uia import UIAElement, UIATree

    send_btn = UIAElement(
        name="Send",
        control_type="Button",
        automation_id="send_button",
        class_name="",
        rect=(500, 500, 600, 530),
        is_enabled=True,
        is_visible=True,
        patterns=["invoke"],
        value="",
        depth=2,
    )
    subject_field = UIAElement(
        name="Subject",
        control_type="Edit",
        automation_id="compose_subject",
        class_name="",
        rect=(100, 100, 700, 130),
        is_enabled=True,
        is_visible=True,
        patterns=["value"],
        value="",
        depth=2,
    )
    attachment_btn = UIAElement(
        name="Attach",
        control_type="Button",
        automation_id="",
        class_name="",
        rect=(10, 50, 80, 70),
        is_enabled=True,
        is_visible=True,
        patterns=["invoke"],
        value="",
        depth=2,
    )
    toolbar = UIAElement(
        name="Compose toolbar",
        control_type="ToolBar",
        automation_id="",
        class_name="",
        rect=(0, 40, 800, 80),
        is_enabled=True,
        is_visible=True,
        patterns=[],
        value="",
        children=[attachment_btn],
        depth=1,
    )
    root = UIAElement(
        name="New Message",
        control_type="Window",
        automation_id="",
        class_name="",
        rect=(0, 0, 800, 600),
        is_enabled=True,
        is_visible=True,
        patterns=[],
        value="",
        children=[toolbar, subject_field, send_btn],
        depth=0,
    )
    return UIATree(
        root=root,
        window_title="New Message",
        app_name="olk.exe",
        timestamp=time.time(),
        pid=1234,
        hwnd=12345,
    )


class TestUIAGrounder:
    """Tests for grounder/uia_grounder.py"""

    def test_ground_by_automation_id_hint(self) -> None:
        """Descriptions with explicit automation_id: should use exact ID matching."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("automation_id:send_button", tree)
        assert result is not None
        assert result.method == "uia"
        assert result.uia_element is not None
        assert result.uia_element.name == "Send"
        assert result.confidence >= 0.9

    def test_ground_by_exact_name(self) -> None:
        """Grounding should find exact name matches with high confidence."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("Send", tree)
        assert result is not None
        assert result.uia_element is not None
        assert result.uia_element.name == "Send"

    def test_ground_button_description(self) -> None:
        """'the Send button' should find the Send button."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("the Send button", tree)
        assert result is not None
        assert result.uia_element is not None
        assert "Send" in result.uia_element.name

    def test_ground_returns_none_for_missing(self) -> None:
        """Grounding should return None when no element matches."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("the non-existent element", tree)
        assert result is None

    def test_ground_confidence_range(self) -> None:
        """Confidence should always be between 0.0 and 1.0."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("Subject field", tree)
        if result:
            assert 0.0 <= result.confidence <= 1.0

    def test_grounded_element_has_coordinates(self) -> None:
        """GroundedElement should have valid centre coordinates."""
        from windowsagent.grounder.uia_grounder import ground
        tree = _make_test_tree()
        result = ground("Send", tree)
        assert result is not None
        cx, cy = result.coordinates
        assert cx > 0
        assert cy > 0

    def test_extract_type_hints(self) -> None:
        """Type hint extraction should identify control types from descriptions."""
        from windowsagent.grounder.uia_grounder import _extract_type_hint
        assert _extract_type_hint("click the button") == "Button"
        assert _extract_type_hint("type into the text box") == "Edit"
        assert _extract_type_hint("the dropdown menu") == "ComboBox"
        assert _extract_type_hint("tick the checkbox") == "CheckBox"
        assert _extract_type_hint("some random text") is None

    def test_clean_description(self) -> None:
        """_clean_description should strip filler words."""
        from windowsagent.grounder.uia_grounder import _clean_description
        cleaned = _clean_description("the Send button")
        assert "send" in cleaned
        # "the" and "button" are filler words that get stripped
        assert "the" not in cleaned.split()


class TestHybridGrounder:
    """Tests for grounder/hybrid.py"""

    def test_hybrid_uses_uia_first(self) -> None:
        """hybrid.ground should use UIA grounding first."""
        from windowsagent.grounder import ground
        from windowsagent.observer.state import AppState
        from windowsagent.observer.uia import UIATree, UIAElement
        from windowsagent.observer.screenshot import Screenshot
        from windowsagent.config import Config
        from PIL import Image

        tree = _make_test_tree()

        # Build a minimal AppState
        mock_screenshot = Screenshot(
            image=Image.new("RGB", (800, 600)),
            dpi_scale=1.0,
            timestamp=time.time(),
            monitor_index=0,
            logical_width=800,
            logical_height=600,
            physical_width=800,
            physical_height=600,
        )
        state = AppState(
            uia_tree=tree,
            screenshot=mock_screenshot,
            window_title="Test",
            app_name="test.exe",
            pid=0,
            hwnd=0,
            timestamp=time.time(),
        )

        config = Config(vision_model="none")  # Disable vision for this test
        result = ground("Send", state, config)

        assert result is not None
        assert result.method == "uia"

    def test_hybrid_returns_none_when_no_match(self) -> None:
        """hybrid.ground should return None when all methods fail."""
        from windowsagent.grounder import ground
        from windowsagent.observer.state import AppState
        from windowsagent.observer.uia import UIATree, UIAElement
        from windowsagent.observer.screenshot import Screenshot
        from windowsagent.config import Config
        from PIL import Image

        tree = _make_test_tree()
        mock_screenshot = Screenshot(
            image=Image.new("RGB", (800, 600)),
            dpi_scale=1.0,
            timestamp=time.time(),
            monitor_index=0,
            logical_width=800,
            logical_height=600,
            physical_width=800,
            physical_height=600,
        )
        state = AppState(
            uia_tree=tree,
            screenshot=mock_screenshot,
            window_title="Test",
            app_name="test.exe",
            pid=0,
            hwnd=0,
            timestamp=time.time(),
        )

        config = Config(vision_model="none")  # No vision fallback
        result = ground("xyzzy_nonexistent_element_12345", state, config)
        assert result is None
