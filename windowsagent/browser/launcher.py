"""
Chrome launcher for CDP-based browser grounding.

Launches Chrome with --remote-debugging-port so WindowsAgent can connect
via CDP and extract the accessibility tree + DOM layout without extensions
or manual setup.

Launch strategy (non-destructive — never kills existing Chrome tabs):

1. Check if CDP is already available on the requested port.
   If yes: skip launch entirely and attach to the running instance.

2. If CDP is not available and Chrome is already running (without CDP):
   Launch a SEPARATE Chrome instance with --user-data-dir pointing to a
   temporary directory. This bypasses Chrome's singleton lock and opens a
   new isolated window alongside the existing Chrome session.

3. If Chrome is not running at all:
   Launch Chrome with the requested --profile-directory and CDP enabled.
   The user's real profile (cookies, sessions, extensions) is used.

Note: In cases 1 and 2, the user's existing tabs are never touched.
In case 3, the real profile is used so existing bookmarks/cookies are
available. Saved passwords are not accessible via CDP by design.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx
import psutil

logger = logging.getLogger(__name__)

# Default Chrome install path on Windows
DEFAULT_CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


async def is_cdp_available(cdp_port: int = 9222, timeout: float = 1.5) -> bool:
    """Check if a Chrome CDP endpoint is already listening on the given port.

    Args:
        cdp_port: The port to check.
        timeout: How long to wait for a response.

    Returns:
        True if CDP is responding, False otherwise.
    """
    url = f"http://localhost:{cdp_port}/json/version"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=timeout)
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, OSError):
        return False


def _chrome_is_running() -> bool:
    """Return True if any chrome.exe process is currently running."""
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == "chrome.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def _launch(
    chrome_exe: str,
    cdp_port: int,
    url: str,
    profile_dir: str | None,
    user_data_dir: str | None,
) -> subprocess.Popen[bytes]:
    """Internal: build and run the Chrome command."""
    args = [
        chrome_exe,
        f"--remote-debugging-port={cdp_port}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if user_data_dir:
        args.append(f"--user-data-dir={user_data_dir}")
    elif profile_dir:
        args.append(f"--profile-directory={profile_dir}")
    args.append(url)

    logger.info("Launching Chrome: %s", " ".join(args))
    return subprocess.Popen(args)


def launch_chrome_with_cdp(
    profile_dir: str = "Default",
    cdp_port: int = 9222,
    url: str = "about:blank",
    chrome_exe: str = DEFAULT_CHROME_EXE,
) -> subprocess.Popen[bytes]:
    """Launch Chrome with remote debugging enabled.

    If Chrome is already running (but without CDP), this launches a SEPARATE
    Chrome instance using a temporary --user-data-dir to bypass the singleton
    lock. Existing tabs are never closed.

    If Chrome is not running, launches with the given --profile-directory so
    the user's cookies and sessions are available.

    Args:
        profile_dir: Chrome profile directory name (e.g. "Default", "Profile 12").
            Used only when Chrome is not already running.
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

    if _chrome_is_running():
        # Chrome is running but not with CDP. Open a separate instance alongside
        # the existing one using a temp profile dir to bypass the singleton lock.
        # Existing tabs and windows are unaffected.
        tmp_dir = Path(tempfile.gettempdir()) / f"chrome-cdp-{cdp_port}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Chrome already running — launching isolated CDP instance with temp profile: %s",
            tmp_dir,
        )
        return _launch(
            chrome_exe=chrome_exe,
            cdp_port=cdp_port,
            url=url,
            profile_dir=None,
            user_data_dir=str(tmp_dir),
        )
    else:
        # Chrome is not running — launch fresh with the real profile.
        logger.info("Chrome not running — launching with profile: %s", profile_dir)
        return _launch(
            chrome_exe=chrome_exe,
            cdp_port=cdp_port,
            url=url,
            profile_dir=profile_dir,
            user_data_dir=None,
        )


async def ensure_cdp(
    profile_dir: str = "Default",
    cdp_port: int = 9222,
    url: str = "about:blank",
    chrome_exe: str = DEFAULT_CHROME_EXE,
    launch_timeout: float = 15.0,
) -> tuple[bool, subprocess.Popen[bytes] | None]:
    """Ensure a Chrome CDP endpoint is available. Attach if already up, launch if not.

    This is the recommended entry point for server.py. It avoids killing existing
    Chrome sessions by checking CDP availability first.

    Returns:
        (ready, proc) where ready=True if CDP is available, proc is the launched
        process handle or None if we attached to an existing instance.
    """
    # Step 1: check if CDP is already up — skip launch entirely
    if await is_cdp_available(cdp_port):
        logger.info("CDP already available on port %d — skipping launch", cdp_port)
        return True, None

    # Step 2: CDP not available — launch Chrome (non-destructively)
    proc = launch_chrome_with_cdp(
        profile_dir=profile_dir,
        cdp_port=cdp_port,
        url=url,
        chrome_exe=chrome_exe,
    )

    ready = await wait_for_cdp(cdp_port=cdp_port, timeout=launch_timeout)
    return ready, proc


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
