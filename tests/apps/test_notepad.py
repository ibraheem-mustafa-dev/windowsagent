"""
Integration tests for the Notepad app profile.

These tests open real instances of Windows Notepad and exercise the
full observe/act/verify pipeline. All tests are marked integration.

Run with:
    pytest tests/apps/test_notepad.py -v
"""

from __future__ import annotations

import time

import pytest


@pytest.mark.integration
class TestNotepadProfile:
    """Full integration tests for Notepad automation."""

    @pytest.fixture(autouse=True)
    def notepad_app(self):
        """Open a fresh Notepad for each test, terminate after."""
        from windowsagent.config import load_config
        from windowsagent.apps.notepad import open as notepad_open, clear

        config = load_config()
        app = notepad_open(config=config)
        yield app, config
        # Close Notepad without saving
        try:
            from windowsagent.actor.input_actor import hotkey, press_key
            hotkey("alt", "f4")
            time.sleep(0.3)
            # Handle "Save?" dialog
            try:
                press_key("n")  # Don't save
            except Exception:
                pass
        except Exception:
            pass

    def test_open_notepad(self, notepad_app) -> None:
        """Notepad should open successfully."""
        app, config = notepad_app
        assert app is not None

    def test_type_and_retrieve_text(self, notepad_app) -> None:
        """Should type text and retrieve it back."""
        from windowsagent.apps.notepad import type_text, get_text

        app, config = notepad_app
        test_text = "Hello from WindowsAgent integration test"

        type_text(app, test_text, config)
        time.sleep(0.3)

        retrieved = get_text(app, config)
        assert test_text in retrieved, f"Expected {test_text!r} in {retrieved!r}"

    def test_clear_text(self, notepad_app) -> None:
        """Should clear all text from Notepad."""
        from windowsagent.apps.notepad import type_text, clear, get_text

        app, config = notepad_app
        type_text(app, "This text will be cleared", config)
        time.sleep(0.2)
        clear(app, config)
        time.sleep(0.2)

        text = get_text(app, config)
        assert text.strip() == "", f"Expected empty text after clear, got: {text!r}"

    def test_select_all(self, notepad_app) -> None:
        """select_all should not raise and should work."""
        from windowsagent.apps.notepad import type_text, select_all

        app, config = notepad_app
        type_text(app, "Select all test text", config)
        time.sleep(0.2)
        result = select_all(app, config)
        assert result is True

    def test_agent_act_type(self, notepad_app) -> None:
        """Agent.act() type action should work with Notepad."""
        from windowsagent.agent import Agent
        from windowsagent.apps.notepad import get_text

        app, config = notepad_app
        agent = Agent(config)

        result = agent.act(
            "Notepad",
            action="type",
            target="Text Editor",
            params={"text": "Agent act test"},
        )

        assert result.success, f"act() failed: {result.error}"
        time.sleep(0.3)

        text = get_text(app, config)
        assert "Agent act test" in text
