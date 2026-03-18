"""
Result dataclasses for the WindowsAgent Agent class.

Extracted from agent.py to keep that module under the 250-line limit.
These are part of the public API — import them from windowsagent.agent (re-exported).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from windowsagent.grounder.uia_grounder import GroundedElement


@dataclass
class ActionResult:
    """Result of a single Agent.act() call."""

    success: bool
    action: str
    target: str
    error: str = ""
    error_type: str = ""
    grounded_element: GroundedElement | None = None
    diff_pct: float = 0.0
    duration_ms: float = 0.0


@dataclass
class VerifyResult:
    """Result of a single Agent.verify() call."""

    success: bool
    diff_pct: float
    changed_elements: int = 0


@dataclass
class TaskResult:
    """Result of a complete Agent.run() task (Phase 2)."""

    success: bool
    task: str
    steps_completed: int
    total_steps: int
    error: str = ""
    duration_ms: float = 0.0
