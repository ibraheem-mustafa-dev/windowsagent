"""
Workflow replay — execute recorded JSONL action sequences.

Loads a JSONL recording file, substitutes variables in parameters,
and executes each step via the Agent API.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def load_workflow(path: str) -> list[dict[str, Any]]:
    """Load a JSONL workflow file into a list of action steps."""
    steps: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON at line %d: %s", line_num, exc)
    return steps


def substitute_variables(
    params: dict[str, Any],
    variables: dict[str, str],
) -> dict[str, Any]:
    """Replace ${variable} placeholders in params with provided values."""
    result: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            missing = [
                m.group(1)
                for m in _VAR_PATTERN.finditer(value)
                if m.group(1) not in variables
            ]
            if missing:
                raise ValueError(f"Missing variable(s): {', '.join(missing)}")
            result[key] = _VAR_PATTERN.sub(lambda m: variables[m.group(1)], value)
        else:
            result[key] = value
    return result


def run_workflow(
    path: str,
    variables: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Execute a recorded JSONL workflow.

    Args:
        path: Path to the JSONL recording file.
        variables: Variable substitutions for parameterised workflows.

    Returns:
        List of step results.
    """
    from windowsagent.agent import Agent
    from windowsagent.config import load_config

    steps = load_workflow(path)
    if not steps:
        raise ValueError(f"No steps found in {path}")

    config = load_config()
    agent = Agent(config)
    vars_ = variables or {}
    results: list[dict[str, Any]] = []

    for i, step in enumerate(steps):
        window = step.get("window", "")
        action = step.get("action", "")
        element = step.get("element", "")
        params = step.get("params", {})

        # Substitute variables
        if params:
            params = substitute_variables(params, vars_)

        logger.info("Replay step %d/%d: %s on %r", i + 1, len(steps), action, element)

        try:
            result = agent.act(window, action, element, params)
            results.append({
                "step": i + 1,
                "success": result.success,
                "action": action,
                "element": element,
                "error": result.error,
            })
        except Exception as exc:
            results.append({
                "step": i + 1,
                "success": False,
                "action": action,
                "element": element,
                "error": str(exc),
            })
            logger.warning("Replay step %d failed: %s", i + 1, exc)

    return results
