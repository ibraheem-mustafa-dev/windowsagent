"""
Browser grounding routes for the WindowsAgent HTTP server.

Handles /browser/* endpoints — open, observe, act, screenshot, close.
Browser state (grounder + Chrome PID) is managed via _server_state.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import windowsagent._server_state as _state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/browser")


class BrowserOpenRequest(BaseModel):
    profile: str = "Default"
    url: str = "about:blank"
    cdp_port: int = 9222


class BrowserObserveRequest(BaseModel):
    include_all: bool = False


class BrowserActRequest(BaseModel):
    action: str  # "click" | "type" | "scroll" | "key" | "navigate"
    index: int = -1
    text: str = ""
    url: str = ""
    keys: str = ""
    direction: str = "down"
    amount: int = 300


@router.post("/open")
async def browser_open(request: BrowserOpenRequest) -> dict[str, Any]:
    """Launch Chrome with CDP and connect the browser grounder.

    Launches Chrome with --remote-debugging-port, waits for CDP to be ready,
    then connects BrowserGrounding. Returns the CDP URL and Chrome PID.
    """
    from windowsagent.browser.grounder import BrowserGrounding
    from windowsagent.browser.launcher import ensure_cdp

    # Close existing connection if any
    if _state.browser_grounder is not None:
        try:
            await _state.browser_grounder.close()
        except Exception:
            pass
        _state.browser_grounder = None

    try:
        ready, proc = await ensure_cdp(
            profile_dir=request.profile,
            cdp_port=request.cdp_port,
            url=request.url,
        )
        if proc is not None:
            _state.browser_chrome_pid = proc.pid

        if not ready:
            return {
                "success": False,
                "error": f"Chrome CDP not ready on port {request.cdp_port} after timeout",
            }

        cdp_url = f"http://localhost:{request.cdp_port}"
        _state.browser_grounder = BrowserGrounding()
        await _state.browser_grounder.attach_to_existing(cdp_url)

        return {
            "success": True,
            "cdp_url": cdp_url,
            "pid": _state.browser_chrome_pid,
        }
    except Exception as exc:
        _state.browser_grounder = None
        _state.browser_chrome_pid = None
        return {"success": False, "error": str(exc)}


@router.post("/observe")
async def browser_observe(request: BrowserObserveRequest) -> dict[str, Any]:
    """Capture the current browser page as a structured VirtualPage.

    Returns the URL, title, elements (with integer indices), and page text.
    Each element includes role, name, bounding box, and interactivity flags.
    """
    if _state.browser_grounder is None or not _state.browser_grounder.is_connected:
        raise HTTPException(
            status_code=400, detail="No browser connection — call /browser/open first"
        )

    try:
        page = await _state.browser_grounder.capture_virtual_page()
        elements = []
        for el in page.elements:
            if not request.include_all and el.index < 0:
                continue
            elements.append({
                "index": el.index,
                "role": el.role,
                "name": el.name,
                "tag": el.tag,
                "x": el.x,
                "y": el.y,
                "width": el.width,
                "height": el.height,
                "value": el.value,
                "placeholder": el.placeholder,
                "href": el.href,
                "is_in_viewport": el.is_in_viewport,
                "needs_vision_fallback": el.needs_vision_fallback,
            })
        return {
            "url": page.url,
            "title": page.title,
            "elements": elements,
            "page_text": page.page_text,
            "scroll_x": page.scroll_x,
            "scroll_y": page.scroll_y,
            "viewport_width": page.viewport_width,
            "viewport_height": page.viewport_height,
            "llm_prompt": page.to_llm_prompt(interactable_only=not request.include_all),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/act")
async def browser_act(request: BrowserActRequest) -> dict[str, Any]:
    """Execute a browser action: click, type, scroll, key, or navigate."""
    if _state.browser_grounder is None or not _state.browser_grounder.is_connected:
        raise HTTPException(
            status_code=400, detail="No browser connection — call /browser/open first"
        )

    try:
        if request.action == "navigate":
            await _state.browser_grounder.navigate(request.url)
            return {"success": True, "error": None}

        if request.action == "scroll":
            await _state.browser_grounder.scroll(
                direction=request.direction,
                amount=request.amount,
            )
            return {"success": True, "error": None}

        if request.action == "key":
            await _state.browser_grounder.press_keys(request.keys)
            return {"success": True, "error": None}

        # Actions that need an element index: click, type
        if request.index < 0:
            return {
                "success": False,
                "error": f"Action '{request.action}' requires a valid element index",
            }

        # Look up element from a fresh capture
        page = await _state.browser_grounder.capture_virtual_page()
        element = page.find_by_index(request.index)
        if element is None:
            return {
                "success": False,
                "error": f"Element index {request.index} not found on current page",
            }

        if request.action == "click":
            await _state.browser_grounder.click_element(element)
        elif request.action == "type":
            await _state.browser_grounder.type_into_element(element, request.text)
        else:
            return {"success": False, "error": f"Unknown action: {request.action}"}

        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/screenshot")
async def browser_screenshot(element_index: int = -1) -> dict[str, Any]:
    """Take a screenshot of the viewport or a specific element.

    Query params:
        element_index: If >= 0, screenshot only that element's bounding box.
                       If -1 (default), screenshot the full viewport.

    Returns base64-encoded PNG.
    """
    if _state.browser_grounder is None or not _state.browser_grounder.is_connected:
        raise HTTPException(
            status_code=400, detail="No browser connection — call /browser/open first"
        )

    try:
        if element_index >= 0:
            page = await _state.browser_grounder.capture_virtual_page()
            element = page.find_by_index(element_index)
            if element is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Element index {element_index} not found",
                )
            png_bytes = await _state.browser_grounder.screenshot_element(element)
        else:
            png_bytes = await _state.browser_grounder.screenshot_viewport()

        return {
            "success": True,
            "image_base64": base64.b64encode(png_bytes).decode("ascii"),
            "content_type": "image/png",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/close")
async def browser_close() -> dict[str, Any]:
    """Close the CDP connection and optionally kill the Chrome process."""
    if _state.browser_grounder is not None:
        try:
            await _state.browser_grounder.close()
        except Exception:
            pass
        _state.browser_grounder = None

    # Optionally kill Chrome
    if _state.browser_chrome_pid is not None:
        try:
            import psutil
            proc = psutil.Process(_state.browser_chrome_pid)
            proc.terminate()
            logger.info("Terminated Chrome process %d", _state.browser_chrome_pid)
        except Exception:
            pass
        _state.browser_chrome_pid = None

    return {"success": True}
