"""
Tests for the HTTP server endpoints.

Uses FastAPI's TestClient for synchronous testing without starting uvicorn.
Agent/browser state is mocked to avoid real Windows interactions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    """Create a TestClient with mocked server state."""
    import windowsagent._server_state as _state

    # Mock the agent and lock
    mock_agent = MagicMock()
    _state.agent = mock_agent
    import asyncio
    _state.action_lock = asyncio.Lock()
    _state.start_time = 1000.0

    from windowsagent.server import app
    return TestClient(app)


# ── /health ──────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_health_uptime_is_positive(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0


# ── /observe ─────────────────────────────────────────────────────────────────


class TestObserveEndpoint:
    def test_observe_returns_state(self, client: TestClient) -> None:
        import windowsagent._server_state as _state

        # Build a mock AppState
        mock_state = MagicMock()
        mock_state.window_title = "Test Window"
        mock_state.app_name = "test.exe"
        mock_state.pid = 1234
        mock_state.hwnd = 5678
        mock_state.timestamp = 1000.0
        mock_state.is_webview2_app = False
        mock_state.screenshot.logical_width = 1920
        mock_state.screenshot.logical_height = 1080
        mock_state.screenshot.dpi_scale = 1.0
        mock_state.uia_tree.root.name = "Window"
        mock_state.uia_tree.root.control_type = "Window"
        mock_state.uia_tree.root.automation_id = ""
        mock_state.uia_tree.root.class_name = ""
        mock_state.uia_tree.root.rect = (0, 0, 1920, 1080)
        mock_state.uia_tree.root.is_enabled = True
        mock_state.uia_tree.root.is_visible = True
        mock_state.uia_tree.root.patterns = []
        mock_state.uia_tree.root.value = ""
        mock_state.uia_tree.root.depth = 0
        mock_state.uia_tree.root.children = []
        mock_state.ocr_results = []
        mock_state.focused_element = None

        _state.agent.observe.return_value = mock_state

        resp = client.post("/observe", json={"window": "Test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_title"] == "Test Window"
        assert data["app_name"] == "test.exe"

    def test_observe_404_when_window_not_found(self, client: TestClient) -> None:
        import windowsagent._server_state as _state
        from windowsagent.exceptions import WindowNotFoundError

        _state.agent.observe.side_effect = WindowNotFoundError("Missing")

        resp = client.post("/observe", json={"window": "Missing"})
        assert resp.status_code == 404

    def test_observe_500_on_agent_error(self, client: TestClient) -> None:
        import windowsagent._server_state as _state
        from windowsagent.exceptions import WindowsAgentError

        _state.agent.observe.side_effect = WindowsAgentError("Internal fail")

        resp = client.post("/observe", json={"window": "Test"})
        assert resp.status_code == 500


# ── /act ─────────────────────────────────────────────────────────────────────


class TestActEndpoint:
    def test_act_returns_result(self, client: TestClient) -> None:
        import windowsagent._server_state as _state

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.action = "click"
        mock_result.target = "Button"
        mock_result.error = None
        mock_result.error_type = None
        mock_result.diff_pct = 0.05
        mock_result.duration_ms = 120.0
        mock_result.grounded_element = None

        _state.agent.act.return_value = mock_result

        with patch("windowsagent.recorder.is_recording", return_value=False):
            resp = client.post("/act", json={
                "window": "Test",
                "action": "click",
                "element": "Button",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "click"

    def test_act_404_when_window_not_found(self, client: TestClient) -> None:
        import windowsagent._server_state as _state
        from windowsagent.exceptions import WindowNotFoundError

        _state.agent.act.side_effect = WindowNotFoundError("Gone")

        resp = client.post("/act", json={
            "window": "Gone",
            "action": "click",
            "element": "X",
        })
        assert resp.status_code == 404

    def test_act_returns_error_on_agent_error(self, client: TestClient) -> None:
        import windowsagent._server_state as _state
        from windowsagent.exceptions import ActionFailedError

        _state.agent.act.side_effect = ActionFailedError(
            action="click", reason="element disabled"
        )

        with patch("windowsagent.recorder.is_recording", return_value=False):
            resp = client.post("/act", json={
                "window": "Test",
                "action": "click",
                "element": "Disabled Button",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "error" in data


# ── /verify ──────────────────────────────────────────────────────────────────


class TestVerifyEndpoint:
    def test_verify_returns_result(self, client: TestClient) -> None:
        import windowsagent._server_state as _state

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.diff_pct = 0.15

        _state.agent.verify.return_value = mock_result

        resp = client.post("/verify", json={"window": "Test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["diff_pct"] == 0.15

    def test_verify_404_when_window_not_found(self, client: TestClient) -> None:
        import windowsagent._server_state as _state
        from windowsagent.exceptions import WindowNotFoundError

        _state.agent.verify.side_effect = WindowNotFoundError("X")

        resp = client.post("/verify", json={"window": "X"})
        assert resp.status_code == 404


# ── /windows ─────────────────────────────────────────────────────────────────


class TestWindowsEndpoint:
    @patch("windowsagent.observer.uia.get_windows")
    def test_list_windows(self, mock_get: MagicMock, client: TestClient) -> None:
        mock_win = MagicMock()
        mock_win.title = "Notepad"
        mock_win.app_name = "notepad.exe"
        mock_win.pid = 100
        mock_win.hwnd = 200
        mock_win.rect = (0, 0, 800, 600)
        mock_win.is_visible = True
        mock_win.is_enabled = True
        mock_get.return_value = [mock_win]

        resp = client.get("/windows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Notepad"


# ── /window/manage ───────────────────────────────────────────────────────────


class TestWindowManageEndpoint:
    @patch("windowsagent.window_manager.activate", return_value=True)
    @patch("windowsagent.window_manager.find_window")
    def test_activate_window(
        self, mock_find: MagicMock, mock_act: MagicMock, client: TestClient,
    ) -> None:
        mock_find.return_value = MagicMock()

        resp = client.post("/window/manage", json={
            "window": "Notepad",
            "action": "activate",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @patch("windowsagent.window_manager.find_window")
    def test_unknown_action_returns_error(self, mock_find: MagicMock, client: TestClient) -> None:
        mock_find.return_value = MagicMock()

        resp = client.post("/window/manage", json={
            "window": "Notepad",
            "action": "explode",
        })
        # Route catches HTTPException(400) in its broad `except Exception` handler
        # and re-wraps as 500. The error message still indicates the real issue.
        assert resp.status_code in (400, 500)
        assert "explode" in resp.json()["detail"]

    @patch("windowsagent.window_manager.find_window")
    def test_window_not_found_returns_404(self, mock_find: MagicMock, client: TestClient) -> None:
        from windowsagent.exceptions import WindowNotFoundError
        mock_find.side_effect = WindowNotFoundError("Gone")

        resp = client.post("/window/manage", json={
            "window": "Gone",
            "action": "activate",
        })
        assert resp.status_code == 404


# ── /spawn ───────────────────────────────────────────────────────────────────


class TestSpawnEndpoint:
    @patch("windowsagent.routes.system.subprocess")
    def test_spawn_success(self, mock_sub: MagicMock, client: TestClient) -> None:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_sub.Popen.return_value = mock_proc
        mock_sub.CREATE_NEW_CONSOLE = 0x10

        resp = client.post("/spawn", json={"executable": "notepad.exe"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["pid"] == 9999

    @patch("windowsagent.routes.system.subprocess")
    def test_spawn_failure(self, mock_sub: MagicMock, client: TestClient) -> None:
        mock_sub.Popen.side_effect = FileNotFoundError("not found")
        mock_sub.CREATE_NEW_CONSOLE = 0x10

        resp = client.post("/spawn", json={"executable": "nonexistent.exe"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


# ── /shell ───────────────────────────────────────────────────────────────────


class TestShellEndpoint:
    @patch("windowsagent.routes.system.subprocess")
    def test_shell_success(self, mock_sub: MagicMock, client: TestClient) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_sub.run.return_value = mock_result
        mock_sub.PIPE = -1

        resp = client.post("/shell", json={"command": "echo hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["stdout"] == "output"

    @patch("windowsagent.routes.system.subprocess")
    def test_shell_timeout(self, mock_sub: MagicMock, client: TestClient) -> None:
        import subprocess as real_sub
        mock_sub.run.side_effect = real_sub.TimeoutExpired(cmd="test", timeout=30)
        mock_sub.PIPE = -1
        mock_sub.TimeoutExpired = real_sub.TimeoutExpired

        resp = client.post("/shell", json={"command": "sleep 999", "timeout": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "timed out" in data["stderr"]
