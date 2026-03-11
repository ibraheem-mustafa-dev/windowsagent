"""
Action Recorder — records every /act and /task call to a JSONL file.

When config.record_replays is True, each action is appended as a single
JSON line to a timestamped file in config.replay_dir. This is the
foundation for Phase 3 replay functionality.

File format (one JSON object per line):
    {"timestamp": 1710000000.0, "window": "Notepad", "action": "type",
     "element": "Text Editor", "params": {"text": "Hello"}, "result": {"success": true}}
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state — the active recording file path
_recording_path: Path | None = None


def start_recording(replay_dir: str) -> Path:
    """Start a new recording session.

    Creates the replay directory if needed and opens a new JSONL file
    with a timestamp-based name.

    Args:
        replay_dir: Directory to store replay files.

    Returns:
        Path to the new recording file.
    """
    global _recording_path

    dir_path = Path(replay_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    _recording_path = dir_path / f"recording_{timestamp}.jsonl"
    logger.info("Recording started: %s", _recording_path)
    return _recording_path


def record_action(
    window: str,
    action: str,
    element: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Append a single action record to the current recording file.

    Does nothing if recording is not active.

    Args:
        window: Window title.
        action: Action type (click, type, scroll, etc.).
        element: Target element description.
        params: Action parameters.
        result: Action result dict.
    """
    if _recording_path is None:
        return

    record = {
        "timestamp": time.time(),
        "window": window,
        "action": action,
        "element": element,
        "params": params,
        "result": result,
    }

    try:
        with _recording_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.warning("Failed to write recording: %s", exc)


def is_recording() -> bool:
    """Check if recording is currently active."""
    return _recording_path is not None


def get_recording_path() -> Path | None:
    """Get the path to the current recording file, or None."""
    return _recording_path


def stop_recording() -> Path | None:
    """Stop recording and return the path to the recording file."""
    global _recording_path
    path = _recording_path
    _recording_path = None
    if path:
        logger.info("Recording stopped: %s", path)
    return path
