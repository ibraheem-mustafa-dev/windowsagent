"""
MCP server for WindowsAgent.

Exposes WindowsAgent capabilities as MCP tools for Claude Desktop,
Cursor, and any MCP-compatible AI tool. Uses FastMCP with stdio transport.

The server communicates with the existing FastAPI backend on localhost:7862
via HTTP. Start the FastAPI server first: windowsagent serve

Usage:
    python -m windowsagent.mcp_server
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:7862"

mcp = FastMCP(
    "WindowsAgent",
    instructions="AI agent that controls Windows desktop apps via the UI Automation API. "
    "Reads the UI by name, not by pixel.",
)


def _post(path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the WindowsAgent FastAPI backend."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{BASE_URL}{path}", json=data or {})
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result


def _get(path: str) -> Any:
    """GET from the WindowsAgent FastAPI backend."""
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{BASE_URL}{path}")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def wa_health() -> str:
    """Check if the WindowsAgent server is running and healthy."""
    result = _get("/health")
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_list_windows() -> str:
    """List all visible top-level windows on the desktop.

    Returns window titles, process names, and PIDs.
    """
    result = _get("/windows")
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_observe(window: str) -> str:
    """Capture the current state of a window: UIA tree, screenshot metadata, and OCR text.

    Args:
        window: Window title or partial match (e.g. "Excel", "Notepad")
    """
    result = _post("/observe", {"window": window})
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_act(
    window: str, action: str, element: str, text: str = "", key: str = ""
) -> str:
    """Execute a single action on a UI element in a window.

    Args:
        window: Window title or partial match
        action: Action type — click, type, scroll, key, expand, toggle, select
        element: Target element description (e.g. "Save button", "Email text field")
        text: Text to type (for action="type")
        key: Key to press (for action="key", e.g. "enter", "escape")
    """
    params: dict[str, Any] = {}
    if text:
        params["text"] = text
    if key:
        params["key"] = key
    result = _post(
        "/act",
        {
            "window": window,
            "action": action,
            "element": element,
            "params": params,
        },
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_task(window: str, task: str, max_steps: int = 20) -> str:
    """Execute a complete natural language task using the LLM task planner.

    The agent observes the window, plans steps, and executes them with verification.

    Args:
        window: Window title or partial match
        task: Natural language task description (e.g. "Send an email to Amir about the invoice")
        max_steps: Maximum number of steps before stopping (default 20)
    """
    result = _post(
        "/task",
        {
            "window": window,
            "task": task,
            "max_steps": max_steps,
        },
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_manage_window(window: str, action: str) -> str:
    """Manage window state — activate, minimise, maximise, restore, close.

    Args:
        window: Window title or partial match
        action: One of: activate, minimise, maximise, restore, close, bring_to_front
    """
    result = _post(
        "/window/manage",
        {
            "window": window,
            "action": action,
        },
    )
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
