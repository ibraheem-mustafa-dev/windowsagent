"""
System utility routes for the WindowsAgent HTTP server.

Handles /spawn and /shell endpoints — launching processes and running
shell commands in the server's user session.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time as _time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class SpawnRequest(BaseModel):
    executable: str
    args: list[str] = []
    cwd: str = ""


class ShellRequest(BaseModel):
    command: str
    shell: str = "pwsh"       # "pwsh" | "cmd" | "powershell"
    cwd: str = ""
    timeout: int = 30         # seconds
    encoding: str = "utf-8"


@router.post("/spawn")
async def spawn_process(request: SpawnRequest) -> dict[str, Any]:
    """Spawn a visible process in the current user session.

    Uses subprocess.Popen with CREATE_NEW_CONSOLE so the process gets its own
    visible console window. Returns the PID of the spawned process.
    """
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


_SHELLS: dict[str, list[str]] = {
    "pwsh": [r"C:\Program Files\PowerShell\7\pwsh.exe", "-NoProfile", "-NonInteractive", "-Command"],
    "powershell": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"],
    "cmd": ["cmd.exe", "/c"],
}


@router.post("/shell")
async def run_shell(request: ShellRequest) -> dict[str, Any]:
    """Run a shell command in the server's user session and return stdout/stderr.

    For fire-and-forget GUI apps use /spawn instead.
    """
    shell_prefix = _SHELLS.get(request.shell, _SHELLS["pwsh"])
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
