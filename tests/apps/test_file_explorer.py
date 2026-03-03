"""
Integration tests for the File Explorer app profile.

All tests are marked integration and require Windows 10/11 with
File Explorer available (always the case on standard Windows installs).

Run with:
    pytest tests/apps/test_file_explorer.py -v
"""

from __future__ import annotations

import time

import pytest


@pytest.mark.integration
class TestFileExplorerProfile:
    """Integration tests for File Explorer automation."""

    @pytest.fixture(autouse=True)
    def explorer_app(self):
        """Open File Explorer, yield, close after test."""
        from windowsagent.config import load_config
        from windowsagent.apps.file_explorer import open as fe_open

        config = load_config()
        app = fe_open(config=config)
        time.sleep(1.0)
        yield app, config
        try:
            from windowsagent.actor.input_actor import hotkey
            app.top_window().set_focus()
            hotkey("alt", "f4")
        except Exception:
            pass

    def test_open_file_explorer(self, explorer_app) -> None:
        """File Explorer should open successfully."""
        app, config = explorer_app
        assert app is not None

    def test_navigate_to_c_drive(self, explorer_app) -> None:
        """Should navigate to C:\\ successfully."""
        from windowsagent.apps.file_explorer import navigate, list_items

        app, config = explorer_app
        navigate(app, "C:\\", config)
        time.sleep(1.0)

        items = list_items(app, config)
        # C:\ always contains Windows folder
        assert any("windows" in item.lower() for item in items), (
            f"'Windows' folder not found in C:\\ listing: {items}"
        )

    def test_list_items_returns_list(self, explorer_app) -> None:
        """list_items should return a non-empty list."""
        from windowsagent.apps.file_explorer import navigate, list_items

        app, config = explorer_app
        navigate(app, "C:\\", config)
        time.sleep(0.8)

        items = list_items(app, config)
        assert isinstance(items, list)
        assert len(items) > 0, "Expected at least one item in C:\\"

    def test_navigate_to_user_home(self, explorer_app) -> None:
        """Should navigate to the user's home folder."""
        import os
        from windowsagent.apps.file_explorer import navigate, list_items

        app, config = explorer_app
        home = os.path.expanduser("~")
        navigate(app, home, config)
        time.sleep(1.0)

        items = list_items(app, config)
        assert isinstance(items, list)
        # Home folder should have some items (Documents, Downloads, etc.)
