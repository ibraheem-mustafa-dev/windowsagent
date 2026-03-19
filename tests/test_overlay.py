"""Tests for UIA element overlay."""
from __future__ import annotations


class TestColourMapping:
    def test_button_is_blue(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type

        r, g, b, _a = colour_for_control_type("Button")
        assert (r, g, b) == (66, 133, 244)

    def test_edit_is_green(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type

        r, g, b, _a = colour_for_control_type("Edit")
        assert (r, g, b) == (52, 168, 83)

    def test_list_is_orange(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type

        r, g, b, _a = colour_for_control_type("List")
        assert (r, g, b) == (251, 188, 4)

    def test_unknown_is_grey(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type

        r, g, b, _a = colour_for_control_type("SomeCustomControl")
        assert (r, g, b) == (154, 160, 166)

    def test_alpha_is_semi_transparent(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type

        _r, _g, _b, a = colour_for_control_type("Button")
        assert a == 60


class TestFlattenTree:
    def test_flattens_nested_elements(self) -> None:
        from windowsagent.overlay.renderer import flatten_elements

        tree = {
            "name": "root",
            "control_type": "Window",
            "rect": [0, 0, 100, 100],
            "is_visible": True,
            "children": [
                {
                    "name": "btn",
                    "control_type": "Button",
                    "rect": [10, 10, 50, 30],
                    "is_visible": True,
                    "children": [],
                },
                {
                    "name": "hidden",
                    "control_type": "Text",
                    "rect": [0, 0, 0, 0],
                    "is_visible": False,
                    "children": [],
                },
            ],
        }
        visible = flatten_elements(tree)
        assert len(visible) == 2
        names = [e["name"] for e in visible]
        assert "btn" in names
        assert "hidden" not in names

    def test_skips_zero_rect_elements(self) -> None:
        from windowsagent.overlay.renderer import flatten_elements

        tree = {
            "name": "root",
            "control_type": "Window",
            "rect": [0, 0, 1920, 1080],
            "is_visible": True,
            "children": [
                {
                    "name": "zero",
                    "control_type": "Pane",
                    "rect": [0, 0, 0, 0],
                    "is_visible": True,
                    "children": [],
                },
            ],
        }
        visible = flatten_elements(tree)
        assert len(visible) == 1


from unittest.mock import MagicMock, patch


class TestDataFetcher:
    def test_fetch_windows_returns_list(self) -> None:
        from windowsagent.overlay.renderer import fetch_windows

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "Notepad", "hwnd": 123, "rect": [0, 0, 800, 600]},
        ]
        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_resp
            windows = fetch_windows()
        assert len(windows) == 1
        assert windows[0]["title"] == "Notepad"

    def test_fetch_uia_tree_direct_shape(self) -> None:
        """Real API shape: uia_tree IS the root element (no 'root' wrapper)."""
        from windowsagent.overlay.renderer import fetch_uia_tree

        tree_data = {
            "uia_tree": {
                "name": "Notepad",
                "control_type": "Window",
                "rect": [0, 0, 800, 600],
                "is_visible": True,
                "children": [],
            },
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = tree_data
        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = fetch_uia_tree("Notepad")
        assert result is not None
        assert result["name"] == "Notepad"

    def test_fetch_uia_tree_nested_root_shape(self) -> None:
        """Fallback: uia_tree has a nested 'root' key."""
        from windowsagent.overlay.renderer import fetch_uia_tree

        tree_data = {
            "uia_tree": {
                "root": {
                    "name": "App",
                    "control_type": "Window",
                    "rect": [0, 0, 800, 600],
                    "is_visible": True,
                    "children": [],
                },
            },
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = tree_data
        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = fetch_uia_tree("App")
        assert result is not None
        assert result["name"] == "App"

    def test_fetch_uia_tree_returns_none_on_error(self) -> None:
        from windowsagent.overlay.renderer import fetch_uia_tree

        with patch("windowsagent.overlay.renderer.httpx") as mock_httpx:
            mock_httpx.post.side_effect = Exception("Connection refused")
            result = fetch_uia_tree("Notepad")
        assert result is None


class TestDPIScaling:
    def test_scale_rect_at_100_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect

        result = scale_rect((100, 200, 300, 400), dpi_scale=1.0)
        assert result == (100, 200, 300, 400)

    def test_scale_rect_at_150_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect

        result = scale_rect((150, 300, 450, 600), dpi_scale=1.5)
        assert result == (100, 200, 300, 400)

    def test_scale_rect_at_200_percent(self) -> None:
        from windowsagent.overlay.renderer import scale_rect

        result = scale_rect((200, 400, 600, 800), dpi_scale=2.0)
        assert result == (100, 200, 300, 400)


class TestSearchElements:
    def test_search_by_name(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "Save", "control_type": "Button", "automation_id": "btn_save"},
            {"name": "Cancel", "control_type": "Button", "automation_id": "btn_cancel"},
            {"name": "File Name", "control_type": "Edit", "automation_id": "txt_filename"},
        ]
        results = search_elements(elements, "save")
        assert len(results) == 1
        assert results[0]["name"] == "Save"

    def test_search_by_automation_id(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "OK", "control_type": "Button", "automation_id": "dlg_ok"},
            {"name": "Cancel", "control_type": "Button", "automation_id": "dlg_cancel"},
        ]
        results = search_elements(elements, "dlg_ok")
        assert len(results) == 1

    def test_search_by_control_type(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "Save", "control_type": "Button", "automation_id": ""},
            {"name": "Name", "control_type": "Edit", "automation_id": ""},
        ]
        results = search_elements(elements, "edit")
        assert len(results) == 1
        assert results[0]["name"] == "Name"

    def test_empty_query_returns_all(self) -> None:
        from windowsagent.overlay.inspector import search_elements

        elements = [
            {"name": "A", "control_type": "Button", "automation_id": ""},
            {"name": "B", "control_type": "Edit", "automation_id": ""},
        ]
        results = search_elements(elements, "")
        assert len(results) == 2


class TestProfileExport:
    def test_generates_known_element_entry(self) -> None:
        from windowsagent.overlay.inspector import element_to_profile_entry

        elem = {
            "name": "Save",
            "control_type": "Button",
            "automation_id": "btn_save",
            "patterns": ["invoke"],
            "rect": [100, 200, 200, 230],
        }
        entry = element_to_profile_entry(elem)
        assert entry["name"] == "Save"
        assert entry["control_type"] == "Button"
        assert entry["automation_id"] == "btn_save"
        assert "invoke" in entry["patterns"]

    def test_generates_profile_template(self) -> None:
        from windowsagent.overlay.inspector import generate_profile_snippet

        entries = [
            {"name": "Save", "control_type": "Button", "automation_id": "btn_save", "patterns": ["invoke"]},
            {"name": "Name", "control_type": "Edit", "automation_id": "txt_name", "patterns": ["value"]},
        ]
        snippet = generate_profile_snippet("myapp.exe", entries)
        assert "class MyappProfile" in snippet
        assert '"Save"' in snippet
        assert "btn_save" in snippet
        assert "BaseAppProfile" in snippet


from click.testing import CliRunner


class TestOverlayCLI:
    def test_overlay_command_exists(self) -> None:
        from windowsagent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["overlay", "--help"])
        assert result.exit_code == 0
        assert "overlay" in result.output.lower()

    def test_overlay_requires_window(self) -> None:
        from windowsagent.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["overlay"])
        assert result.exit_code != 0
