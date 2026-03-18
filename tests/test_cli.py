"""
Tests for the CLI interface (cli.py).

Uses Click's CliRunner for isolated testing without real Windows interactions.
CLI functions import dependencies inside their function bodies, so patches
target the source modules rather than windowsagent.cli.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from windowsagent.cli import cli


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── version command ──────────────────────────────────────────────────────────


class TestVersionCommand:
    def test_version_shows_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "WindowsAgent v" in result.output

    def test_version_option(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "windowsagent" in result.output


# ── config show command ──────────────────────────────────────────────────────


class TestConfigShowCommand:
    def test_config_show_text(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "WindowsAgent Configuration" in result.output
        assert "vision_api_key" in result.output
        assert "***" in result.output or "(not set)" in result.output

    def test_config_show_json(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["config", "show", "--json-output"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "server_host" in data
        assert data["vision_api_key"] in ("***", "(not set)")


# ── windows command ──────────────────────────────────────────────────────────


class TestWindowsCommand:
    @patch("windowsagent.observer.uia.get_windows")
    def test_windows_no_results(self, mock_get: MagicMock, runner: CliRunner) -> None:
        mock_get.return_value = []
        result = runner.invoke(cli, ["windows"])
        assert result.exit_code == 0
        assert "No visible windows found" in result.output

    @patch("windowsagent.observer.uia.get_windows")
    def test_windows_text_output(self, mock_get: MagicMock, runner: CliRunner) -> None:
        mock_win = MagicMock()
        mock_win.title = "Notepad"
        mock_win.app_name = "notepad.exe"
        mock_win.pid = 100
        mock_win.hwnd = 200
        mock_get.return_value = [mock_win]

        result = runner.invoke(cli, ["windows"])
        assert result.exit_code == 0
        assert "Notepad" in result.output
        assert "notepad.exe" in result.output

    @patch("windowsagent.observer.uia.get_windows")
    def test_windows_json_output(self, mock_get: MagicMock, runner: CliRunner) -> None:
        mock_win = MagicMock()
        mock_win.title = "Test"
        mock_win.app_name = "test.exe"
        mock_win.pid = 42
        mock_win.hwnd = 99
        mock_get.return_value = [mock_win]

        result = runner.invoke(cli, ["windows", "--json-output"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["title"] == "Test"

    @patch("windowsagent.observer.uia.get_windows")
    def test_windows_error(self, mock_get: MagicMock, runner: CliRunner) -> None:
        mock_get.side_effect = RuntimeError("UIA failed")
        result = runner.invoke(cli, ["windows"])
        assert result.exit_code == 1
        assert "Error" in result.output


# ── window manage command ────────────────────────────────────────────────────


class TestWindowManageCommand:
    @patch("windowsagent.window_manager.activate", return_value=True)
    @patch("windowsagent.window_manager.find_window")
    def test_activate_window(
        self, mock_find: MagicMock, mock_act: MagicMock, runner: CliRunner,
    ) -> None:
        mock_find.return_value = MagicMock()
        result = runner.invoke(cli, ["window", "--title", "Notepad", "--action", "activate"])
        assert result.exit_code == 0
        assert "[OK]" in result.output

    @patch("windowsagent.window_manager.find_window")
    def test_window_not_found(self, mock_find: MagicMock, runner: CliRunner) -> None:
        mock_find.side_effect = RuntimeError("not found")
        result = runner.invoke(cli, ["window", "--title", "X", "--action", "activate"])
        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("windowsagent.window_manager.get_geometry")
    @patch("windowsagent.window_manager.find_window")
    def test_geometry_text_output(
        self, mock_find: MagicMock, mock_geom: MagicMock, runner: CliRunner,
    ) -> None:
        mock_win = MagicMock()
        mock_win.title = "Test"
        mock_find.return_value = mock_win

        geom = MagicMock()
        geom.left = 0
        geom.top = 0
        geom.width = 800
        geom.height = 600
        mock_geom.return_value = geom

        result = runner.invoke(cli, ["window", "--title", "Test", "--action", "geometry"])
        assert result.exit_code == 0
        assert "800x600" in result.output

    @patch("windowsagent.window_manager.get_geometry")
    @patch("windowsagent.window_manager.find_window")
    def test_geometry_json_output(
        self, mock_find: MagicMock, mock_geom: MagicMock, runner: CliRunner,
    ) -> None:
        mock_find.return_value = MagicMock()

        geom = MagicMock()
        geom.left = 10
        geom.top = 20
        geom.width = 1024
        geom.height = 768
        mock_geom.return_value = geom

        result = runner.invoke(cli, [
            "window", "--title", "Test", "--action", "geometry", "--json-output",
        ])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["width"] == 1024

    @patch("windowsagent.window_manager.minimise", return_value=False)
    @patch("windowsagent.window_manager.find_window")
    def test_action_failure(
        self, mock_find: MagicMock, mock_min: MagicMock, runner: CliRunner,
    ) -> None:
        mock_find.return_value = MagicMock()
        result = runner.invoke(cli, ["window", "--title", "Test", "--action", "minimise"])
        assert result.exit_code == 1
        assert "[FAIL]" in result.output

    @patch("windowsagent.window_manager.maximise", return_value=True)
    @patch("windowsagent.window_manager.find_window")
    def test_action_json_success(
        self, mock_find: MagicMock, mock_max: MagicMock, runner: CliRunner,
    ) -> None:
        mock_find.return_value = MagicMock()
        result = runner.invoke(cli, [
            "window", "--title", "Test", "--action", "maximise", "--json-output",
        ])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["success"] is True


# ── observe command ──────────────────────────────────────────────────────────


class TestObserveCommand:
    @patch("windowsagent.agent.Agent")
    @patch("windowsagent.config.load_config")
    def test_observe_error(
        self, mock_config: MagicMock, mock_agent_cls: MagicMock, runner: CliRunner,
    ) -> None:
        mock_agent = MagicMock()
        mock_agent.observe.side_effect = RuntimeError("fail")
        mock_agent_cls.return_value = mock_agent

        result = runner.invoke(cli, ["observe", "--window", "X"])
        assert result.exit_code == 1
        assert "Error" in result.output


# ── act command ──────────────────────────────────────────────────────────────


class TestActCommand:
    @patch("windowsagent.agent.Agent")
    @patch("windowsagent.config.load_config")
    def test_act_success(
        self, mock_config: MagicMock, mock_agent_cls: MagicMock, runner: CliRunner,
    ) -> None:
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.diff_pct = 0.1
        mock_result.duration_ms = 50.0
        mock_result.error = None
        mock_agent.act.return_value = mock_result
        mock_agent_cls.return_value = mock_agent

        result = runner.invoke(cli, [
            "act", "--window", "Notepad", "--action", "click", "--element", "Button",
        ])
        assert result.exit_code == 0
        assert "[OK]" in result.output

    @patch("windowsagent.agent.Agent")
    @patch("windowsagent.config.load_config")
    def test_act_failure(
        self, mock_config: MagicMock, mock_agent_cls: MagicMock, runner: CliRunner,
    ) -> None:
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "element not found"
        mock_agent.act.return_value = mock_result
        mock_agent_cls.return_value = mock_agent

        result = runner.invoke(cli, [
            "act", "--window", "Notepad", "--action", "click", "--element", "Missing",
        ])
        assert result.exit_code == 1
        assert "[FAIL]" in result.output

    @patch("windowsagent.agent.Agent")
    @patch("windowsagent.config.load_config")
    def test_act_json_output(
        self, mock_config: MagicMock, mock_agent_cls: MagicMock, runner: CliRunner,
    ) -> None:
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.action = "type"
        mock_result.target = "Editor"
        mock_result.error = None
        mock_result.diff_pct = 0.5
        mock_result.duration_ms = 200.0
        mock_agent.act.return_value = mock_result
        mock_agent_cls.return_value = mock_agent

        result = runner.invoke(cli, [
            "act", "--window", "Notepad", "--action", "type",
            "--element", "Editor", "--text", "Hello", "--json-output",
        ])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["success"] is True

    @patch("windowsagent.agent.Agent")
    @patch("windowsagent.config.load_config")
    def test_act_error(
        self, mock_config: MagicMock, mock_agent_cls: MagicMock, runner: CliRunner,
    ) -> None:
        mock_agent = MagicMock()
        mock_agent.act.side_effect = RuntimeError("crash")
        mock_agent_cls.return_value = mock_agent

        result = runner.invoke(cli, [
            "act", "--window", "Test", "--action", "click", "--element", "X",
        ])
        assert result.exit_code == 1
        assert "Error" in result.output
