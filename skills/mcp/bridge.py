"""WindowsAgent MCP Bridge — exposes WindowsAgent HTTP API as MCP tools.

Usage:
    pip install mcp httpx
    python bridge.py

Configure in Claude Desktop or Cursor MCP settings (see windowsagent.json).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import run_server
from mcp.types import TextContent, Tool

BASE_URL = os.environ.get("WA_BASE_URL", "http://localhost:7862")

server = Server("windowsagent")


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=120.0)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="wa_observe",
            description=(
                "Observe a window's current state. Returns the UIA accessibility tree, "
                "OCR text, and a base64 screenshot. Always call this before acting on "
                "an unfamiliar window to discover element names."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Window title to observe (e.g. 'Notepad', 'Google Chrome')",
                    },
                },
                "required": ["window"],
            },
        ),
        Tool(
            name="wa_act",
            description=(
                "Execute a UI action on a window element. Supported actions: "
                "click, type, key, scroll. Use 'element' to target a specific UIA "
                "element by name (run wa_observe first to discover names)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Window title",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["click", "type", "key", "scroll"],
                        "description": "Action to perform",
                    },
                    "element": {
                        "type": "string",
                        "description": "UIA element name to target (from wa_observe)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type (for 'type' action)",
                    },
                    "keys": {
                        "type": "string",
                        "description": "Key combo to send (for 'key' action, e.g. 'ctrl,s')",
                    },
                    "x": {
                        "type": "integer",
                        "description": "X coordinate for click (optional, prefer element name)",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate for click (optional, prefer element name)",
                    },
                },
                "required": ["window", "action"],
            },
        ),
        Tool(
            name="wa_task",
            description=(
                "Execute a complete natural language task. WindowsAgent uses an LLM "
                "to decompose the task into atomic UI actions and executes them. "
                "Best for multi-step operations like 'open file, edit text, save'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Window title to operate on",
                    },
                    "task": {
                        "type": "string",
                        "description": "Natural language task description",
                    },
                },
                "required": ["window", "task"],
            },
        ),
        Tool(
            name="wa_shell",
            description=(
                "Run a shell command in the user's Windows session and return "
                "stdout/stderr. Runs PowerShell 7 by default. Use for file operations, "
                "git commands, process management, and anything that doesn't need a GUI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30)",
                        "default": 30,
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="wa_spawn",
            description=(
                "Launch a visible interactive process in the user's desktop session. "
                "Use for opening apps like Notepad, Chrome, VS Code, or Windows Terminal."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "exe": {
                        "type": "string",
                        "description": "Executable or command to launch (e.g. 'notepad.exe', 'code .')",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional command-line arguments",
                    },
                },
                "required": ["exe"],
            },
        ),
        Tool(
            name="wa_health",
            description=(
                "Check if the WindowsAgent server is running. Returns status and version. "
                "Call this first if other tools are failing."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [TextContent(type="text", text=str(result))]
    except httpx.ConnectError:
        return [
            TextContent(
                type="text",
                text="ERROR: Cannot connect to WindowsAgent at "
                f"{BASE_URL}. Is the server running? "
                "Start it with: windowsagent serve",
            )
        ]
    except Exception as exc:
        return [TextContent(type="text", text=f"ERROR: {exc}")]


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    with _client() as client:
        if name == "wa_health":
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()

        if name == "wa_observe":
            resp = client.post("/observe", json={"window": args["window"]})
            resp.raise_for_status()
            data = resp.json()
            # Strip base64 screenshot from response to save context tokens
            data.pop("screenshot", None)
            return data

        if name == "wa_act":
            payload: dict[str, Any] = {
                "window": args["window"],
                "action": args["action"],
            }
            if args.get("element"):
                payload["element"] = args["element"]
            params: dict[str, Any] = {}
            if args.get("text"):
                params["text"] = args["text"]
            if args.get("keys"):
                params["keys"] = args["keys"]
            if args.get("x") is not None:
                params["x"] = args["x"]
            if args.get("y") is not None:
                params["y"] = args["y"]
            if params:
                payload["params"] = params
            resp = client.post("/act", json=payload)
            resp.raise_for_status()
            return resp.json()

        if name == "wa_task":
            resp = client.post(
                "/task",
                json={"window": args["window"], "task": args["task"]},
                timeout=300.0,
            )
            resp.raise_for_status()
            return resp.json()

        if name == "wa_shell":
            resp = client.post(
                "/shell",
                json={
                    "command": args["command"],
                    "timeout": args.get("timeout", 30),
                },
            )
            resp.raise_for_status()
            return resp.json()

        if name == "wa_spawn":
            command = args["exe"]
            if args.get("args"):
                command += " " + " ".join(args["args"])
            resp = client.post("/spawn", json={"command": command})
            resp.raise_for_status()
            return resp.json()

        return {"error": f"Unknown tool: {name}"}


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_server(server))
