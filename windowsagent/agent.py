"""
Agent — main orchestration loop for WindowsAgent.

The Agent class ties all modules together. In Phase 1, it provides:
- observe(): Capture the current state of a window
- act(): Execute a single action on a named element
- verify(): Check if a state change occurred

The full Observe-Plan-Act-Verify loop (agent.run()) requires the task
planner, which is not implemented until Phase 2. Direct use of act() is
the Phase 1 interface.

Example:
    from windowsagent import Agent

    agent = Agent()
    state = agent.observe("Notepad")
    result = agent.act("Notepad", action="type", target="Text Editor", params={"text": "Hello"})
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from windowsagent.config import SENSITIVE_ACTION_KEYWORDS, Config, load_config
from windowsagent.exceptions import (
    ActionFailedError,
    GroundingFailedError,
    WindowsAgentError,
)

if TYPE_CHECKING:
    from windowsagent.grounder.uia_grounder import GroundedElement
    from windowsagent.observer.state import AppState
    from windowsagent.observer.uia import UIAElement

logger = logging.getLogger(__name__)


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


class Agent:
    """Main WindowsAgent orchestration class.

    Creates an Agent with optional custom config. If no config is provided,
    load_config() is called to load from env vars / config files.

    Args:
        config: Optional pre-built Config instance. If None, load_config() is used.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self._setup_logging()
        logger.info("WindowsAgent initialised (vision_model=%r)", self.config.vision_model)

    def _setup_logging(self) -> None:
        """Configure logging level from config."""
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    def observe(self, window_title: str) -> AppState:
        """Capture the current state of a window.

        Activates the window via pywinctl before capturing to ensure it is
        in the foreground and not minimised.

        Args:
            window_title: Partial window title to match.

        Returns:
            AppState with UIA tree, screenshot, and metadata.

        Raises:
            WindowNotFoundError: If no matching window is found.
            ObserverError: If both screenshot and UIA capture fail.
        """
        from windowsagent.observer.state import capture

        # Activate the target window before observing (ensures foreground + visible)
        try:
            from windowsagent.window_manager import activate
            activate(window_title, wait=True)
        except Exception as exc:
            logger.debug("Pre-observe activation failed (continuing): %s", exc)

        logger.info("Observing window %r", window_title)
        return capture(window_title, self.config)

    def act(
        self,
        window_title: str,
        action: str,
        target: str,
        params: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Execute a single action on a named element in a window.

        The full pipeline:
        1. Capture current state (observe)
        2. Ground the target description to a UI element
        3. Select app profile
        4. Execute the action via UIA or input fallback
        5. Return result

        Verification is NOT run by act() — call verify() separately if needed.

        Args:
            window_title: Partial window title.
            action: Action type: "click", "type", "scroll", "key", "expand", "toggle", "select"
            target: Natural language description of target element.
            params: Action-specific parameters:
                - type: {"text": "Hello World"}
                - scroll: {"direction": "down", "amount": 3}
                - key: {"key": "enter"} or {"keys": ["ctrl", "s"]}

        Returns:
            ActionResult with success flag, grounded element, and diff_pct.
        """
        if params is None:
            params = {}

        start_time = time.monotonic()

        # Safety check for sensitive actions
        if self.config.confirm_sensitive:
            if any(kw in target.lower() for kw in SENSITIVE_ACTION_KEYWORDS):
                logger.warning(
                    "Sensitive action detected: action=%r target=%r — skipping (confirm_sensitive=True)",
                    action,
                    target,
                )
                return ActionResult(
                    success=False,
                    action=action,
                    target=target,
                    error=f"Action blocked: target {target!r} matches sensitive keywords. "
                    "Set config.confirm_sensitive=False to allow.",
                    error_type="sensitive_blocked",
                )

        # Step 1: Observe
        try:
            state = self.observe(window_title)
        except WindowsAgentError as exc:
            return ActionResult(
                success=False,
                action=action,
                target=target,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Step 2: Ground the target (for non-keyboard actions)
        grounded: GroundedElement | None = None
        if action not in ("key",):
            try:
                from windowsagent.grounder.hybrid import ground
                grounded = ground(target, state, self.config)
                if grounded is None:
                    raise GroundingFailedError(target, methods_tried=["uia"])
            except WindowsAgentError as exc:
                return ActionResult(
                    success=False,
                    action=action,
                    target=target,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # Step 3: Select app profile
        from windowsagent.apps import get_profile
        profile = get_profile(state.app_name, state.window_title)

        # Step 4: Pre-action hook
        element = grounded.uia_element if grounded else None
        try:
            profile.on_before_act(action, element)
        except Exception as exc:
            logger.debug("on_before_act raised: %s", exc)

        # Step 5: Execute action
        success = False
        error = ""
        error_type = ""

        try:
            success = self._execute_action(action, grounded, element, params, state, profile)
        except WindowsAgentError as exc:
            error = str(exc)
            error_type = type(exc).__name__
            logger.warning("Action %r on %r failed: %s", action, target, exc)
        except Exception as exc:
            error = f"Unexpected error: {exc}"
            error_type = "UnexpectedError"
            logger.error("Unexpected error in act(): %s", exc, exc_info=True)

        # Step 6: Post-action hook
        try:
            profile.on_after_act(action, element, success)
        except Exception as exc:
            logger.debug("on_after_act raised: %s", exc)

        # Step 7: Focus restore for apps that steal focus (Outlook, Teams, WebView2)
        if success and profile.requires_focus_restore():
            try:
                from windowsagent.window_manager import activate
                activate(window_title, wait=True)
                logger.debug("Focus restored to %r (profile requires it)", window_title)
            except Exception as exc:
                logger.debug("Focus restore failed (non-fatal): %s", exc)

        duration_ms = (time.monotonic() - start_time) * 1000
        return ActionResult(
            success=success,
            action=action,
            target=target,
            error=error,
            error_type=error_type,
            grounded_element=grounded,
            duration_ms=duration_ms,
        )

    def verify(self, window_title: str, expected_change: str = "") -> VerifyResult:
        """Check if a state change occurred in a window.

        Captures current state and compares to the previous state if available.
        Also runs wait_for_change to allow async updates to settle.

        Args:
            window_title: Partial window title.
            expected_change: Optional description of what should have changed.

        Returns:
            VerifyResult with success flag and diff_pct.
        """
        try:
            state = self.observe(window_title)
            from windowsagent.verifier.verify import wait_for_change
            changed = wait_for_change(state.hwnd, self.config)
            return VerifyResult(success=changed, diff_pct=0.0 if not changed else 0.05)
        except WindowsAgentError as exc:
            logger.warning("Verify failed: %s", exc)
            return VerifyResult(success=False, diff_pct=0.0)

    def run(
        self,
        task: str,
        window_title: str,
        max_steps: int = 20,
    ) -> TaskResult:
        """Execute a complete natural language task.

        Orchestrates the full Observe-Plan-Act-Verify loop:
        1. Observe the target window
        2. Plan the task into ActionSteps via LLM
        3. Execute each step, verifying after each one
        4. Return a summary of what happened

        Args:
            task: Natural language task description.
            window_title: Target window.
            max_steps: Maximum number of steps to execute (default 20).

        Returns:
            TaskResult with success flag, steps completed, and timing.
        """
        from windowsagent.planner.task_planner import PlanningError, TaskPlanner

        start_time = time.monotonic()
        planner = TaskPlanner(self.config)
        step_results: list[dict[str, object]] = []

        # Step 1: Observe
        try:
            state = self.observe(window_title)
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

        # Step 3: Execute each step
        for i, step in enumerate(steps[:max_steps]):
            logger.info(
                "Step %d/%d: %s on %r",
                i + 1, total_steps, step.action_type, step.target_description,
            )

            # Map ActionStep to act() parameters
            params = dict(step.parameters)
            action = step.action_type

            # Handle special action types
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
                # Read is observe-only, no action needed
                step_results.append({
                    "step": i + 1,
                    "action": "read",
                    "target": step.target_description,
                    "success": True,
                })
                completed += 1
                continue

            # Execute via agent.act()
            result = self.act(window_title, action, step.target_description, params)
            step_results.append({
                "step": i + 1,
                "action": action,
                "target": step.target_description,
                "success": result.success,
                "error": result.error,
                "duration_ms": result.duration_ms,
            })

            if result.success:
                completed += 1
                logger.info("Step %d/%d succeeded", i + 1, total_steps)
            else:
                logger.warning(
                    "Step %d/%d failed: %s", i + 1, total_steps, result.error,
                )
                # Stop on failure — caller can inspect step_results
                break

            # Brief pause between steps for UI to settle
            time.sleep(0.3)

        duration_ms = (time.monotonic() - start_time) * 1000
        success = completed == total_steps

        task_result = TaskResult(
            success=success,
            task=task,
            steps_completed=completed,
            total_steps=total_steps,
            error="" if success else f"Failed at step {completed + 1}",
            duration_ms=duration_ms,
        )
        # Attach step details for the /task endpoint
        task_result._step_results = step_results  # type: ignore[attr-defined]
        return task_result

    # ── Private helpers ────────────────────────────────────────────────────

    def _execute_action(
        self,
        action: str,
        grounded: GroundedElement | None,
        element: UIAElement | None,
        params: dict[str, Any],
        state: AppState,
        profile: Any | None = None,
    ) -> bool:
        """Dispatch to the appropriate actor based on action type and profile strategy."""
        from windowsagent.actor import input_actor, uia_actor

        if action == "click":
            if element:
                return uia_actor.click(element, self.config)
            if grounded:
                return input_actor.click_at(*grounded.coordinates, config=self.config)
            return False

        elif action == "type":
            text = str(params.get("text", ""))
            if not text:
                raise ActionFailedError(action="type", reason="No 'text' param provided")
            return self._execute_type(text, element, grounded, state, profile)

        elif action == "scroll":
            direction = str(params.get("direction", "down"))
            amount = int(params.get("amount", 3))
            return self._execute_scroll(direction, amount, element, grounded, state, profile)


        elif action == "key":
            keys = params.get("keys") or [params.get("key", "")]
            if isinstance(keys, str):
                keys = [keys]
            if len(keys) == 1:
                return input_actor.press_key(keys[0], config=self.config)
            return input_actor.hotkey(*keys, config=self.config)

        elif action == "expand":
            if element:
                return uia_actor.expand(element, self.config)
            return False

        elif action == "toggle":
            if element:
                return uia_actor.toggle(element, self.config)
            return False

        elif action == "select":
            if element:
                return uia_actor.select(element, self.config)
            return False

        elif action in ("activate", "minimise", "minimize", "maximise", "maximize", "restore"):
            from windowsagent import window_manager
            normalised = action.replace("minimize", "minimise").replace("maximize", "maximise")
            fn_map = {
                "activate": window_manager.activate,
                "minimise": window_manager.minimise,
                "maximise": window_manager.maximise,
                "restore": window_manager.restore,
            }
            fn = fn_map.get(normalised)
            if fn is None:
                return False
            return fn(state.window_title)

        else:
            raise ActionFailedError(
                action=action,
                reason=f"Unknown action type {action!r}. "
                "Supported: click, type, scroll, key, expand, toggle, select, "
                "activate, minimise, maximise, restore",
                retryable=False,
            )

    def _execute_type(
        self,
        text: str,
        element: UIAElement | None,
        grounded: GroundedElement | None,
        state: AppState,
        profile: Any | None,
    ) -> bool:
        """Execute a type action, respecting the profile's text input strategy."""
        from windowsagent.actor import input_actor, uia_actor

        strategy = profile.get_text_input_strategy() if profile else "value_pattern"

        if strategy == "clipboard" and element:
            # Profile says always use clipboard (Chrome, Edge, Teams, WebView2)
            from windowsagent.actor.clipboard import paste_to_element
            return paste_to_element(element, text, self.config)

        if element:
            return uia_actor.type_text(element, text, self.config, window_hwnd=state.hwnd)

        if grounded:
            input_actor.click_at(*grounded.coordinates, config=self.config)
            if strategy == "clipboard":
                from windowsagent.actor.clipboard import set_text
                set_text(text)
                return input_actor.hotkey("ctrl", "v", config=self.config)
            return input_actor.type_text(text, config=self.config)

        return False

    def _execute_scroll(
        self,
        direction: str,
        amount: int,
        element: UIAElement | None,
        grounded: GroundedElement | None,
        state: AppState,
        profile: Any | None,
    ) -> bool:
        """Execute a scroll action, respecting the profile's scroll strategy."""
        from windowsagent.actor import input_actor, uia_actor

        strategy = profile.get_scroll_strategy() if profile else "scroll_pattern"

        if strategy == "webview2":
            # WebView2 apps: mouse wheel doesn't reach inner content.
            # Click in content area + send Page Down/Up keys.
            from windowsagent.observer.uia import get_window
            try:
                window = get_window(hwnd=state.hwnd)
                from windowsagent.apps.webview2 import scroll_content
                return scroll_content(window, direction, amount, self.config)
            except Exception as exc:
                logger.debug("WebView2 scroll failed, falling back to keyboard: %s", exc)
                key = "page_down" if direction == "down" else "page_up"
                for _ in range(amount):
                    input_actor.press_key(key, config=self.config)
                return True

        if strategy == "keyboard":
            key = "page_down" if direction == "down" else "page_up"
            for _ in range(amount):
                input_actor.press_key(key, config=self.config)
            return True

        # Default: UIA ScrollPattern or coordinate-based
        if element:
            return uia_actor.scroll(element, direction, amount, self.config)
        if grounded:
            return input_actor.scroll_at(
                *grounded.coordinates, direction=direction, amount=amount, config=self.config,
            )
        return False
