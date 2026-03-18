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

import logging
import time
from typing import Any

import uvicorn
from fastapi import FastAPI

from windowsagent import __version__
from windowsagent.config import load_config

import windowsagent._server_state as _state

logger = logging.getLogger(__name__)

app = FastAPI(
    title="WindowsAgent",
    description="Open-source AI agent for Windows desktop automation",
    version=__version__,
    docs_url="/docs",
    redoc_url=None,
)

# ── Route registration ────────────────────────────────────────────────────────

from windowsagent.routes.agent import router as _agent_router
from windowsagent.routes.browser import router as _browser_router
from windowsagent.routes.system import router as _system_router
from windowsagent.routes.window import router as _window_router

app.include_router(_agent_router)
app.include_router(_browser_router)
app.include_router(_system_router)
app.include_router(_window_router)


# ── Startup / shutdown ────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup_event() -> None:
    import asyncio
    from windowsagent.agent import Agent
    _state.agent = Agent()
    _state.action_lock = asyncio.Lock()
    _state.start_time = time.time()
    logger.info("WindowsAgent server started (v%s)", __version__)


# ── Core endpoints ────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint. Always returns 200 when the server is running."""
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round(time.time() - _state.start_time, 1),
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
