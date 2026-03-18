"""
Task execution loop for the WindowsAgent Agent class.

Extracted from agent.py to keep that module under the 250-line limit.
Not part of the public API — use Agent.run() instead.

Integrates RecoveryManager for:
- Focus loss recovery (re-activate window, retry once)
- Unexpected dialog detection and dismissal
- Circuit breaker (stop after N consecutive failures)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from windowsagent.agent_types import TaskResult
from windowsagent.exceptions import WindowsAgentError
from windowsagent.recovery import RecoveryManager

if TYPE_CHECKING:
    from windowsagent.agent import Agent
    from windowsagent.config import Config

logger = logging.getLogger(__name__)


def run_task(
    agent: Agent,
    task: str,
    window_title: str,
    max_steps: int = 20,
) -> TaskResult:
    """Execute a complete natural language task.

    Orchestrates the full Observe-Plan-Act-Verify loop:
    1. Observe the target window
    2. Plan the task into ActionSteps via LLM
    3. Execute each step with error recovery
    4. Return a summary of what happened
    """
    from windowsagent.planner.task_planner import PlanningError, TaskPlanner

    start_time = time.monotonic()
    planner = TaskPlanner(agent.config)
    step_results: list[dict[str, Any]] = []
    recovery = RecoveryManager(window_title=window_title)

    # Step 1: Observe
    try:
        state = agent.observe(window_title)
    except WindowsAgentError as exc:
        return TaskResult(
            success=False,
            task=task,
            steps_completed=0,
            total_steps=0,
            error=f"Observe failed: {exc}",
            duration_ms=(time.monotonic() - start_time) * 1000,
        )

    # Step 2: Plan
    try:
        steps = planner.plan(task, state)
    except (PlanningError, WindowsAgentError) as exc:
        return TaskResult(
            success=False,
            task=task,
            steps_completed=0,
            total_steps=0,
            error=f"Planning failed: {exc}",
            duration_ms=(time.monotonic() - start_time) * 1000,
        )

    if not steps:
        return TaskResult(
            success=False,
            task=task,
            steps_completed=0,
            total_steps=0,
            error="Planner returned no steps — task may not be achievable with visible UI",
            duration_ms=(time.monotonic() - start_time) * 1000,
        )

    total_steps = min(len(steps), max_steps)
    completed = 0

    # Step 3: Execute each step with recovery
    for i, step in enumerate(steps[:max_steps]):
        logger.info(
            "Step %d/%d: %s on %r",
            i + 1, total_steps, step.action_type, step.target_description,
        )

        params = dict(step.parameters)
        action = step.action_type

        # Handle special action types that don't need grounding
        if action == "wait":
            seconds = float(str(params.get("seconds", 1)))
            time.sleep(seconds)
            step_results.append({
                "step": i + 1,
                "action": "wait",
                "target": step.target_description,
                "success": True,
            })
            completed += 1
            continue

        if action == "read":
            step_results.append({
                "step": i + 1,
                "action": "read",
                "target": step.target_description,
                "success": True,
            })
            completed += 1
            continue

        # Execute via agent.act()
        result = agent.act(window_title, action, step.target_description, params)
        step_entry: dict[str, Any] = {
            "step": i + 1,
            "action": action,
            "target": step.target_description,
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }
        step_results.append(step_entry)

        if result.success:
            recovery.record_success()
            completed += 1
            logger.info("Step %d/%d succeeded", i + 1, total_steps)
        else:
            recovery.record_failure(result.error)
            logger.warning(
                "Step %d/%d failed: %s", i + 1, total_steps, result.error,
            )

            # Attempt focus recovery before giving up on this step
            if recovery.attempt_focus_recovery():
                logger.info("Step %d: retrying after focus recovery", i + 1)
                retry = agent.act(window_title, action, step.target_description, params)
                if retry.success:
                    recovery.record_success()
                    completed += 1
                    step_entry["success"] = True
                    step_entry["recovered"] = True
                    logger.info("Step %d succeeded after focus recovery", i + 1)
                    time.sleep(0.3)
                    continue
                else:
                    recovery.record_failure(retry.error)

            # Check for blocking dialogs and try to dismiss
            dialog = recovery.detect_unexpected_dialog()
            if dialog:
                recovery.dismiss_dialog(dialog)
                logger.info("Step %d: dismissed dialog %r", i + 1, dialog)

            # Circuit breaker: stop if too many consecutive failures
            if recovery.is_tripped():
                logger.error(
                    "Circuit breaker tripped after %d consecutive failures — stopping task",
                    recovery.consecutive_failures,
                )
                break

            break

        time.sleep(0.3)

    duration_ms = (time.monotonic() - start_time) * 1000
    success = completed == total_steps

    error_msg = "" if success else f"Failed at step {completed + 1}"
    if recovery.is_tripped():
        error_msg = (
            f"Circuit breaker tripped after {recovery.consecutive_failures} "
            f"consecutive failures at step {completed + 1}"
        )

    task_result = TaskResult(
        success=success,
        task=task,
        steps_completed=completed,
        total_steps=total_steps,
        error=error_msg,
        duration_ms=duration_ms,
    )
    task_result._step_results = step_results  # type: ignore[attr-defined]
    return task_result
