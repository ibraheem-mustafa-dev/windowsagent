"""
Task Planner — LLM-based task decomposition.

Decomposes a natural language task into a list of ActionSteps using either
Gemini Flash (primary) or Claude Haiku (fallback). The planner summarises
the current AppState into a compact text format and asks the LLM to return
a JSON array of action steps.

Usage:
    from windowsagent.planner.task_planner import TaskPlanner

    planner = TaskPlanner(config)
    steps = planner.plan("Open the File menu and click Save", state)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from windowsagent.exceptions import WindowsAgentError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.state import AppState

logger = logging.getLogger(__name__)


class PlanningError(WindowsAgentError):
    """Task planning failed."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message, retryable=retryable)


@dataclass
class ActionStep:
    """A single planned UI action.

    Produced by TaskPlanner and consumed by the Agent loop.
    """

    action_type: Literal["click", "type", "scroll", "key", "select", "read", "wait"]
    target_description: str                    # Natural language ("the Send button")
    parameters: dict[str, object] = field(default_factory=dict)  # text, key, direction, etc.
    expected_result: str = ""                  # What should change ("email sent appears")
    timeout_ms: int = 10_000                   # Max time for this step (ms)


class TaskPlanner:
    """Decomposes a natural language task into a list of ActionSteps.

    Uses Gemini Flash as primary LLM if GEMINI_API_KEY is available,
    falls back to Claude Haiku if ANTHROPIC_API_KEY is available.
    """

    def __init__(self, config: Config) -> None:
        """Initialise the task planner.

        Args:
            config: WindowsAgent configuration. Determines LLM model and API key.
        """
        self.config = config

    def plan(self, task: str, state: AppState) -> list[ActionStep]:
        """Decompose a natural language task into atomic ActionSteps.

        Args:
            task: Natural language task description.
            state: Current application state (provides context for planning).

        Returns:
            Ordered list of ActionSteps.

        Raises:
            PlanningError: If planning fails after retries.
        """
        from windowsagent.planner.prompts import TASK_PLANNER_SYSTEM, build_user_prompt

        state_summary = _summarise_state(state)
        user_prompt = build_user_prompt(task, state_summary)

        # Determine which LLM to use
        gemini_key = os.environ.get("GEMINI_API_KEY", "") or self.config.vision_api_key
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

        raw_json: str = ""
        last_error: Exception | None = None

        # Try up to 2 times with the available LLM
        for attempt in range(2):
            try:
                if gemini_key and self.config.vision_model.startswith("gemini"):
                    raw_json = _call_gemini(
                        TASK_PLANNER_SYSTEM, user_prompt, gemini_key, self.config,
                    )
                elif anthropic_key:
                    raw_json = _call_anthropic(
                        TASK_PLANNER_SYSTEM, user_prompt, anthropic_key, self.config,
                    )
                elif gemini_key:
                    raw_json = _call_gemini(
                        TASK_PLANNER_SYSTEM, user_prompt, gemini_key, self.config,
                    )
                else:
                    raise PlanningError(
                        "No LLM API key available. Set GEMINI_API_KEY or ANTHROPIC_API_KEY.",
                        retryable=False,
                    )
                break
            except PlanningError:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning("Planning attempt %d failed: %s", attempt + 1, exc)
                if attempt < 1:
                    time.sleep(1.0)

        if not raw_json:
            raise PlanningError(
                f"LLM returned no response after retries: {last_error}",
                retryable=True,
            )

        # Parse the JSON response into ActionStep objects
        return _parse_steps(raw_json)

    def replan(
        self,
        task: str,
        state: AppState,
        completed_steps: list[ActionStep],
        error: str,
    ) -> list[ActionStep]:
        """Re-plan after a step failure.

        Provides the LLM with the original task, current state, what was
        already done, and what went wrong — so it can adjust the remaining plan.

        Args:
            task: Original task description.
            state: Current application state after the failure.
            completed_steps: Steps that were successfully executed.
            error: Description of what went wrong.

        Returns:
            New list of remaining ActionSteps.
        """
        from windowsagent.planner.prompts import TASK_PLANNER_SYSTEM

        state_summary = _summarise_state(state)
        completed_summary = "\n".join(
            f"  {i+1}. {s.action_type} on {s.target_description!r} — done"
            for i, s in enumerate(completed_steps)
        )

        user_prompt = (
            f"TASK: {task}\n\n"
            f"COMPLETED STEPS:\n{completed_summary}\n\n"
            f"ERROR: {error}\n\n"
            f"CURRENT APPLICATION STATE:\n{state_summary}\n\n"
            "Given the error above, provide the REMAINING steps to complete "
            "the task. Return a JSON array of action steps."
        )

        gemini_key = os.environ.get("GEMINI_API_KEY", "") or self.config.vision_api_key
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

        raw_json = ""
        try:
            if gemini_key:
                raw_json = _call_gemini(
                    TASK_PLANNER_SYSTEM, user_prompt, gemini_key, self.config,
                )
            elif anthropic_key:
                raw_json = _call_anthropic(
                    TASK_PLANNER_SYSTEM, user_prompt, anthropic_key, self.config,
                )
        except Exception as exc:
            raise PlanningError(f"Replan failed: {exc}", retryable=True) from exc

        if not raw_json:
            raise PlanningError("Replan returned empty response", retryable=True)

        return _parse_steps(raw_json)


# ── LLM backends ────────────────────────────────────────────────────────────


def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    config: Config,
) -> str:
    """Call Gemini Flash via the google.genai SDK.

    Returns the raw text response.
    """
    from google import genai

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    text = response.text or ""
    logger.debug("Gemini response (%d chars): %.200s...", len(text), text)
    return text


def _call_anthropic(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    config: Config,
) -> str:
    """Call Claude Haiku via the anthropic SDK.

    Returns the raw text response.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.1,
    )

    # Extract text from the response
    text = ""
    for block in message.content:
        if hasattr(block, "text"):
            text += block.text

    logger.debug("Anthropic response (%d chars): %.200s...", len(text), text)
    return text


# ── Helpers ──────────────────────────────────────────────────────────────────


def _summarise_state(state: AppState) -> str:
    """Build a compact text summary of AppState for the LLM prompt.

    Includes window title, visible elements (name + control_type), and
    OCR text. Truncated to avoid blowing context windows.
    """
    lines: list[str] = [
        f"Window: {state.window_title!r}",
        f"App: {state.app_name} (PID {state.pid})",
    ]

    # Flatten UIA tree to a list of visible elements (max 100)
    elements: list[str] = []
    _collect_elements(state.uia_tree.root, elements, max_count=100)
    if elements:
        lines.append("Visible UI elements:")
        lines.extend(f"  - {e}" for e in elements)

    # OCR text (first 20 results)
    if state.ocr_results:
        lines.append("OCR text on screen:")
        for r in state.ocr_results[:20]:
            lines.append(f"  - {r.text!r} (confidence {r.confidence:.0%})")

    return "\n".join(lines)


def _collect_elements(
    element: Any,
    out: list[str],
    max_count: int = 100,
    depth: int = 0,
) -> None:
    """Recursively collect element summaries from the UIA tree."""
    if len(out) >= max_count:
        return

    # Skip invisible/unnamed elements at shallow depth
    if element.is_visible and (element.name or element.value):
        indent = "  " * depth
        value_str = f" = {element.value!r}" if element.value else ""
        patterns_str = f" [{', '.join(element.patterns)}]" if element.patterns else ""
        enabled_str = "" if element.is_enabled else " [disabled]"
        out.append(
            f"{indent}{element.control_type} {element.name!r}{value_str}"
            f"{patterns_str}{enabled_str}"
        )

    for child in element.children:
        _collect_elements(child, out, max_count, depth + 1)


def _parse_steps(raw_json: str) -> list[ActionStep]:
    """Parse LLM JSON response into ActionStep objects.

    Handles common LLM response quirks: markdown code fences, trailing
    commas, extra whitespace.

    Raises:
        PlanningError: If JSON parsing fails.
    """
    # Strip markdown code fences if present
    text = raw_json.strip()
    if text.startswith("```"):
        # Remove first and last lines (```json and ```)
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanningError(
            f"LLM returned invalid JSON: {exc}\nResponse: {text[:500]}",
            retryable=True,
        ) from exc

    if not isinstance(data, list):
        raise PlanningError(
            f"Expected JSON array, got {type(data).__name__}",
            retryable=True,
        )

    valid_actions = {"click", "type", "scroll", "key", "select", "read", "wait"}
    steps: list[ActionStep] = []

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict step at index %d", i)
            continue

        action_type = str(item.get("action_type", ""))
        if action_type not in valid_actions:
            logger.warning("Skipping unknown action_type %r at index %d", action_type, i)
            continue

        steps.append(ActionStep(
            action_type=action_type,  # type: ignore[arg-type]
            target_description=str(item.get("target_description", "")),
            parameters=dict(item.get("parameters", {})),
            expected_result=str(item.get("expected_result", "")),
            timeout_ms=int(item.get("timeout_ms", 10_000)),
        ))

    logger.info("Planned %d action steps", len(steps))
    return steps
