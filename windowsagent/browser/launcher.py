"""
Chrome launcher for CDP-based browser grounding.

Launches Chrome with --remote-debugging-port so WindowsAgent can connect
via CDP and extract the accessibility tree + DOM layout without extensions
or manual setup.

Uses the user's existing Chrome profile (cookies, sessions, extensions intact).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Default Chrome install path on Windows
DEFAULT_CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def launch_chrome_with_cdp(
    profile_dir: str = "Default",
    cdp_port: int = 9222,
    url: str = "about:blank",
    chrome_exe: str = DEFAULT_CHROME_EXE,
) -> subprocess.Popen[bytes]:
    """Launch Chrome with remote debugging enabled.

    Args:
        profile_dir: Chrome profile directory name (e.g. "Default", "Profile 12").
        cdp_port: Port for the CDP WebSocket server.
        url: Initial URL to open.
        chrome_exe: Path to chrome.exe.

    Returns:
        The Popen process handle.

    Raises:
        FileNotFoundError: If chrome.exe does not exist at the given path.
    """
    chrome_path = Path(chrome_exe)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found at {chrome_exe}")

    args = [
        chrome_exe,
        f"--remote-debugging-port={cdp_port}",
        f"--profile-directory={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]

    logger.info("Launching Chrome: %s", " ".join(args))
    return subprocess.Popen(args)


async def wait_for_cdp(cdp_port: int = 9222, timeout: float = 15.0) -> bool:
    """Poll http://localhost:{cdp_port}/json until Chrome's CDP is ready.

    Args:
        cdp_port: The CDP port to poll.
        timeout: Maximum seconds to wait.

    Returns:
        True if CDP became available, False if timed out.
    """
    url = f"http://localhost:{cdp_port}/json"
    deadline = asyncio.get_event_loop().time() + timeout
    poll_interval = 0.3

    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await client.get(url, timeout=2.0)
                if resp.status_code == 200:
                    logger.info("CDP ready on port %d", cdp_port)
                    return True
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
                pass
            await asyncio.sleep(poll_interval)

    logger.warning("CDP not ready after %.1fs on port %d", timeout, cdp_port)
    return False
