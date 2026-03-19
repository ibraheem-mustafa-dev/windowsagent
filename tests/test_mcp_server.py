"""Tests for the MCP server tool definitions."""
from __future__ import annotations

import asyncio


class TestMCPToolDefinitions:
    def _get_tool_names(self) -> list[str]:
        from windowsagent.mcp_server import mcp

        return list(mcp._tool_manager._tools.keys())

    def test_observe_tool_exists(self) -> None:
        assert "wa_observe" in self._get_tool_names()

    def test_act_tool_exists(self) -> None:
        assert "wa_act" in self._get_tool_names()

    def test_task_tool_exists(self) -> None:
        assert "wa_task" in self._get_tool_names()

    def test_health_tool_exists(self) -> None:
        assert "wa_health" in self._get_tool_names()

    def test_list_windows_tool_exists(self) -> None:
        assert "wa_list_windows" in self._get_tool_names()

    def test_manage_window_tool_exists(self) -> None:
        assert "wa_manage_window" in self._get_tool_names()

    def test_all_tools_have_descriptions(self) -> None:
        from windowsagent.mcp_server import mcp

        tools = asyncio.run(mcp.list_tools())
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"

    def test_mcp_server_name(self) -> None:
        from windowsagent.mcp_server import mcp

        assert mcp.name == "WindowsAgent"
