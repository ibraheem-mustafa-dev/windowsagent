"""
Agent action routes for the WindowsAgent HTTP server.

Handles /observe, /act, /verify, /task endpoints, the SSE streaming
endpoint, and the _serialise_* helpers used to convert internal types to JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

import windowsagent._server_state as _state
from windowsagent.exceptions import WindowNotFoundError, WindowsAgentError

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────


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
    task: str
    window: str
    max_steps: int = 20


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/observe")
async def observe(request: ObserveRequest) -> dict[str, Any]:
    """Capture the current UIA tree and screenshot for a window."""
    try:
        state = await asyncio.get_event_loop().run_in_executor(
            None, _state.agent.observe, request.window
        )
        return _serialise_app_state(state)
    except WindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WindowsAgentError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/act")
async def act(request: ActRequest) -> dict[str, Any]:
    """Execute a single action on a UI element."""
    assert _state.action_lock is not None
    async with _state.action_lock:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _state.agent.act(
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


@router.post("/verify")
async def verify(request: VerifyRequest) -> dict[str, Any]:
    """Check if a state change occurred in a window."""
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _state.agent.verify(request.window, request.expected_change),
        )
        return {
            "success": result.success,
            "diff_pct": result.diff_pct,
        }
    except WindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/task")
async def run_task(request: TaskRequest) -> dict[str, Any]:
    """Execute a complete natural language task via the LLM task planner."""
    assert _state.action_lock is not None
    async with _state.action_lock:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _state.agent.run(
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
            if hasattr(result, "_step_results"):
                response["steps"] = result._step_results
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


# ── Active element (overlay highlight) ────────────────────────────────────────


@router.get("/agent/active-element")
async def get_active_element() -> dict[str, Any]:
    """Return the automation_id of the element the agent is currently acting on."""
    return {"automation_id": _state.active_element_id}


# ── SSE streaming ─────────────────────────────────────────────────────────────


@router.get("/agent/stream")
async def agent_stream(request: Request) -> EventSourceResponse:
    """Stream agent status events via Server-Sent Events."""

    async def event_generator() -> Any:
        if _state.agent_event_queue is None:
            return
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(
                    _state.agent_event_queue.get(),
                    timeout=30.0,
                )
                yield {
                    "event": event.get("type", "status"),
                    "data": json.dumps(event.get("payload", {})),
                }
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


# ── Serialisation helpers ─────────────────────────────────────────────────────


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
