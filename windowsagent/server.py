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
from fastapi import FastAPI, HTTPException
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
_agent: Any = None
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
    max_steps: int = 20


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
            act_result = {
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
            # Record if recording is active
            from windowsagent.recorder import is_recording, record_action
            if is_recording():
                record_action(
                    window=request.window,
                    action=request.action,
                    element=request.element,
                    params=request.params,
                    result=act_result,
                )
            return act_result
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


class SpawnRequest(BaseModel):
    executable: str
    args: list[str] = []
    cwd: str = ""


class ShellRequest(BaseModel):
    command: str
    shell: str = "pwsh"          # "pwsh" | "cmd" | "powershell"
    cwd: str = ""
    timeout: int = 30            # seconds
    encoding: str = "utf-8"


@app.post("/spawn")
async def spawn_process(request: SpawnRequest) -> dict[str, Any]:
    """Spawn a visible process in the current user session.

    Uses subprocess.Popen with CREATE_NEW_CONSOLE so the process gets its own
    visible console window. Runs in the server's session (session 1 when started
    via the 'WindowsAgent Server' Scheduled Task as an interactive user).

    Returns the PID of the spawned process.
    """
    import subprocess

    try:
        cmd = [request.executable] + request.args
        kwargs: dict[str, Any] = {
            "creationflags": subprocess.CREATE_NEW_CONSOLE,
        }
        if request.cwd:
            kwargs["cwd"] = request.cwd

        proc = subprocess.Popen(cmd, **kwargs)
        return {"success": True, "pid": proc.pid, "cmd": cmd}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/shell")
async def run_shell(request: ShellRequest) -> dict[str, Any]:
    """Run a shell command in the server's user session and return stdout/stderr.

    Runs synchronously (up to request.timeout seconds). Use this when you need
    command output back — e.g. running PowerShell scripts, reading file contents,
    querying system state.

    For fire-and-forget GUI apps use /spawn instead.

    Args:
        command: The command string to execute.
        shell: Interpreter — "pwsh" (PowerShell 7), "powershell" (Windows PS 5),
               or "cmd".
        cwd: Working directory (defaults to user home).
        timeout: Max seconds to wait (default 30).
        encoding: Output encoding (default utf-8).

    Returns:
        {success, stdout, stderr, returncode, duration_ms}
    """
    import subprocess
    import time as _time

    SHELLS: dict[str, list[str]] = {
        "pwsh": [r"C:\Program Files\PowerShell\7\pwsh.exe", "-NoProfile", "-NonInteractive", "-Command"],
        "powershell": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"],
        "cmd": ["cmd.exe", "/c"],
    }

    shell_prefix = SHELLS.get(request.shell, SHELLS["pwsh"])
    cmd = shell_prefix + [request.command]

    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": request.encoding,
        "errors": "replace",
    }
    if request.cwd:
        kwargs["cwd"] = request.cwd

    t0 = _time.monotonic()
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(cmd, timeout=request.timeout, **kwargs),
        )
        duration_ms = (_time.monotonic() - t0) * 1000
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "duration_ms": round(duration_ms, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {request.timeout}s",
            "returncode": -1,
            "duration_ms": round((_time.monotonic() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "duration_ms": 0.0,
        }


@app.post("/task")
async def run_task(request: TaskRequest) -> dict[str, Any]:
    """Execute a complete natural language task.

    Uses the LLM-based TaskPlanner to decompose the task into ActionSteps,
    then executes each step via the Agent loop with verification.
    """
    assert _action_lock is not None
    async with _action_lock:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _agent.run(
                    request.task,
                    request.window,
                    max_steps=request.max_steps,
                ),
            )
            response: dict[str, Any] = {
                "success": result.success,
                "steps_taken": result.steps_completed,
                "total_steps": result.total_steps,
                "error": result.error or None,
                "duration_ms": round(result.duration_ms, 1),
            }
            # Include per-step details if available
            if hasattr(result, "_step_results"):
                response["steps"] = result._step_results
            # Record if recording is active
            from windowsagent.recorder import is_recording, record_action
            if is_recording():
                record_action(
                    window=request.window,
                    action="task",
                    element=request.task,
                    params={"max_steps": request.max_steps},
                    result=response,
                )
            return response
        except WindowNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WindowsAgentError as exc:
            return {
                "success": False,
                "steps_taken": 0,
                "error": str(exc),
            }


# ── Helper functions ─────────────────────────────────────────────────────────


def _serialise_element(element: Any, max_depth: int = 3) -> dict[str, Any]:
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


def _serialise_app_state(state: Any) -> dict[str, Any]:
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
