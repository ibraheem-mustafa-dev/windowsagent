"""
Shared mutable state for the WindowsAgent HTTP server.

Imported by server.py and all route modules. Avoids circular imports
caused by routes needing the agent/browser instances initialised in server.py.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

# Initialised in server.py startup_event()
agent: Any = None
action_lock: asyncio.Lock | None = None

# Initialised on first /browser/open call
browser_grounder: Any = None
browser_chrome_pid: int | None = None

# Server start time for /health uptime reporting
start_time: float = time.time()

# Event queue for SSE streaming — agent_loop pushes events, SSE endpoint reads
agent_event_queue: asyncio.Queue[dict[str, Any]] | None = None
