"""
FastAPI HTTP server for WindowsAgent.

Exposes the agent API over HTTP on localhost:7862. Designed for integration
with OpenClaw and other local tools that call the API.

Security: Binds to 127.0.0.1 only by default. The server warns loudly
if configured to bind on any other interface.

Start with: windowsagent serve
Or: uvicorn windowsagent.server:app --host 127.0.0.1 --port 7862
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from windowsagent import __version__
from windowsagent.config import load_config
from windowsagent.exceptions import WindowNotFoundError, WindowsAgentError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="WindowsAgent",
    description="Open-source AI agent for Windows desktop automation",
    version=__version__,
    docs_url="/docs",
    redoc_url=None,
)

# Global agent instance (initialised on startup)
_agent: "Any" = None
_start_time: float = time.time()
# Per-server lock to serialise pyautogui calls (not thread-safe)
_action_lock: asyncio.Lock | None = None


# ── Pydantic models ──────────────────────────────────────────────────────────


class ObserveRequest(BaseModel):
    window: str


class ActRequest(BaseModel):
    window: str
    action: str
    element: str
    params: dict[str, Any] = {}


class VerifyRequest(BaseModel):
    window: str
    expected_change: str = ""


class TaskRequest(BaseModel):
    window: str
    task: str


# ── Startup / shutdown ───────────────────────────────────────────────────────


@app.on_event("startup")
async def startup_event() -> None:
    global _agent, _action_lock
    from windowsagent.agent import Agent
    _agent = Agent()
    _action_lock = asyncio.Lock()
    logger.info("WindowsAgent server started (v%s)", __version__)


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint. Always returns 200 when the server is running."""
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/windows")
async def list_windows() -> list[dict[str, Any]]:
    """List all visible top-level windows."""
    try:
        from windowsagent.observer.uia import get_windows
        windows = await asyncio.get_event_loop().run_in_executor(None, get_windows)
        return [
            {
                "title": w.title,
                "app_name": w.app_name,
                "pid": w.pid,
                "hwnd": w.hwnd,
                "rect": list(w.rect),
                "is_visible": w.is_visible,
                "is_enabled": w.is_enabled,
            }
            for w in windows
        ]
    except WindowsAgentError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/observe")
async def observe(request: ObserveRequest) -> dict[str, Any]:
    """Capture the current UIA tree and screenshot for a window.

    Returns a serialised AppState with UIA tree, metadata, and OCR results.
    Screenshot is not included in the JSON response (too large); use the
    /screenshot endpoint for that if needed.
    """
    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _agent.observe, request.window
        )
        return _serialise_app_state(state)
    except WindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WindowsAgentError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/act")
async def act(request: ActRequest) -> dict[str, Any]:
    """Execute a single action on a UI element.

    Returns success flag and diff_pct (fraction of screen that changed).
    """
    assert _action_lock is not None
    async with _action_lock:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _agent.act(
                    request.window,
                    request.action,
                    request.element,
                    request.params,
                ),
            )
            return {
                "success": result.success,
                "action": result.action,
                "target": result.target,
                "error": result.error,
                "error_type": result.error_type,
                "diff_pct": result.diff_pct,
                "duration_ms": result.duration_ms,
                "grounding_method": (
                    result.grounded_element.method if result.grounded_element else None
                ),
                "confidence": (
                    result.grounded_element.confidence if result.grounded_element else None
                ),
            }
        except WindowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WindowsAgentError as exc:
            return {"success": False, "error": str(exc), "error_type": type(exc).__name__}


@app.post("/verify")
async def verify(request: VerifyRequest) -> dict[str, Any]:
    """Check if a state change occurred in a window.

    Returns success flag and diff_pct.
    """
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _agent.verify(request.window, request.expected_change),
        )
        return {
            "success": result.success,
            "diff_pct": result.diff_pct,
        }
    except WindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/task")
async def run_task(request: TaskRequest) -> None:
    """Execute a complete natural language task (Phase 2 — not yet implemented)."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Full task execution requires the task planner, which is not implemented "
            "in Phase 1. Use POST /act to execute individual actions."
        ),
    )


# ── Helper functions ─────────────────────────────────────────────────────────


def _serialise_element(element: "Any", max_depth: int = 3) -> dict[str, Any]:
    """Serialise a UIAElement to a JSON-serialisable dict."""
    result: dict[str, Any] = {
        "name": element.name,
        "control_type": element.control_type,
        "automation_id": element.automation_id,
        "class_name": element.class_name,
        "rect": list(element.rect),
        "is_enabled": element.is_enabled,
        "is_visible": element.is_visible,
        "patterns": element.patterns,
        "value": element.value,
        "depth": element.depth,
    }
    if max_depth > 0:
        result["children"] = [
            _serialise_element(child, max_depth - 1) for child in element.children
        ]
    else:
        result["children"] = []
    return result


def _serialise_app_state(state: "Any") -> dict[str, Any]:
    """Serialise an AppState to a JSON-serialisable dict."""
    return {
        "window_title": state.window_title,
        "app_name": state.app_name,
        "pid": state.pid,
        "hwnd": state.hwnd,
        "timestamp": state.timestamp,
        "is_webview2": state.is_webview2_app,
        "screenshot": {
            "width": state.screenshot.logical_width,
            "height": state.screenshot.logical_height,
            "dpi_scale": state.screenshot.dpi_scale,
        },
        "uia_tree": _serialise_element(state.uia_tree.root, max_depth=4),
        "ocr_results": [
            {
                "text": r.text,
                "bounding_box": list(r.bounding_box),
                "confidence": r.confidence,
                "line_index": r.line_index,
            }
            for r in state.ocr_results
        ],
        "focused_element": (
            _serialise_element(state.focused_element, max_depth=0)
            if state.focused_element
            else None
        ),
    }


# ── Entry point ───────────────────────────────────────────────────────────────


def run_server(host: str = "127.0.0.1", port: int = 7862) -> None:
    """Start the HTTP server.

    Args:
        host: Bind host. Keep as 127.0.0.1 for security.
        port: Bind port (default 7862).
    """
    config = load_config()
    actual_host = host or config.server_host
    actual_port = port or config.server_port

    if actual_host != "127.0.0.1":
        logger.warning(
            "WARNING: Server is binding on %s — this exposes WindowsAgent to other "
            "machines on the network. Only do this in a trusted environment.",
            actual_host,
        )

    uvicorn.run(app, host=actual_host, port=actual_port, log_level="info")
