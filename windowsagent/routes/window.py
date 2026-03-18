"""
Window management routes for the WindowsAgent HTTP server.

Handles /windows (list) and /window/manage (activate/minimise/maximise etc.)
using the pywinctl window_manager module.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from windowsagent.exceptions import WindowNotFoundError, WindowsAgentError

logger = logging.getLogger(__name__)
router = APIRouter()


class WindowManageRequest(BaseModel):
    window: str
    action: str  # "activate" | "minimise" | "maximise" | "restore" | "close" | "move" | "resize"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


@router.get("/windows")
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


@router.post("/window/manage")
async def manage_window(request: WindowManageRequest) -> dict[str, Any]:
    """Manage window state — activate, minimise, maximise, restore, close, move, resize.

    Uses pywinctl for reliable cross-platform window management.
    """
    from windowsagent import window_manager

    action = request.action.lower().replace("minimize", "minimise").replace("maximize", "maximise")
    try:
        win = await asyncio.get_event_loop().run_in_executor(
            None, window_manager.find_window, request.window,
        )

        action_map = {
            "activate": lambda: window_manager.activate(win),
            "minimise": lambda: window_manager.minimise(win),
            "maximise": lambda: window_manager.maximise(win),
            "restore": lambda: window_manager.restore(win),
            "close": lambda: window_manager.close(win),
            "move": lambda: window_manager.move(win, request.x, request.y),
            "resize": lambda: window_manager.resize(win, request.width, request.height),
            "bring_to_front": lambda: window_manager.bring_to_front(win),
            "send_to_back": lambda: window_manager.send_to_back(win),
        }

        fn = action_map.get(action)
        if fn is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown window action {request.action!r}. "
                f"Supported: {', '.join(action_map.keys())}",
            )

        result = await asyncio.get_event_loop().run_in_executor(None, fn)
        return {"success": bool(result), "window": request.window, "action": request.action}

    except WindowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
