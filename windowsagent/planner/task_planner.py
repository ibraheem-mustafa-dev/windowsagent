"""
Task Planner — LLM-based task decomposition.

NOT IMPLEMENTED in Phase 1. This module defines the interface and data
structures for Phase 2 implementation.

The TaskPlanner will decompose a natural language task into a list of
ActionSteps that the Agent loop can execute one by one.

Phase 2 implementation will:
1. Accept a task string and current AppState
2. Call a configured LLM (Claude/Gemini) with the system prompt from prompts.py
3. Parse the response into a list of ActionStep objects
4. Return the plan for the agent loop to execute
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.state import AppState


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

    Phase 1: Not implemented. Raises NotImplementedError.
    Phase 2: Will use config.vision_model for LLM-based task planning.
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
            NotImplementedError: Always in Phase 1. Implemented in Phase 2.
        """
        raise NotImplementedError(
            "TaskPlanner.plan() is not implemented in Phase 1. "
            "Use Agent.act() directly to execute individual actions. "
            "Full task planning will be available in Phase 2."
        )
