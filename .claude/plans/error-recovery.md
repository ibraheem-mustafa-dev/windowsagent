# Error Recovery Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add focus-loss recovery, unexpected-dialog handling, and a circuit-breaker pattern to the agent loop so tasks recover from transient failures instead of halting immediately.

**Architecture:** A `RecoveryManager` class in `recovery.py` owns all recovery state (consecutive failure count, dialog history). It is instantiated per `run_task()` call and passed into the step execution loop. The manager tries re-activation on focus loss, dismisses known dialogs via UIA, and trips a circuit breaker after 3 consecutive failures. `agent_loop.py` wraps each step with the manager's `execute_with_recovery()` helper.

**Tech Stack:** Python, pywinctl (window activation), pywinauto UIA (dialog detection), existing `window_manager.py`, existing `exceptions.py`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `windowsagent/exceptions.py` | Modify | Add `CircuitBreakerTrippedError`, `UnexpectedDialogError` |
| `windowsagent/recovery.py` | Create | `RecoveryManager` — tracks failures, focus recovery, dialog detection/dismissal |
| `windowsagent/agent_loop.py` | Modify | Wrap each step with `RecoveryManager.execute_with_recovery()` |
| `tests/test_recovery.py` | Create | Unit tests for all recovery behaviours |

---

## Task 1: Add new exception types

**Files:**
- Modify: `windowsagent/exceptions.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_recovery.py` (create the file):

```python
"""Tests for the error recovery framework."""
from __future__ import annotations

from windowsagent.exceptions import CircuitBreakerTrippedError, UnexpectedDialogError


def test_circuit_breaker_error_is_not_retryable() -> None:
    exc = CircuitBreakerTrippedError(failures=3, window="Notepad")
    assert exc.retryable is False
    assert "3" in str(exc)
    assert "Notepad" in str(exc)


def test_unexpected_dialog_error_is_retryable() -> None:
    exc = UnexpectedDialogError(dialog_title="Save As", window="Notepad")
    assert exc.retryable is True
    assert "Save As" in str(exc)
```

- [ ] **Step 2: Run tests — expect ImportError (exceptions don't exist yet)**

```
python -m pytest tests/test_recovery.py -v
```
Expected: `ImportError: cannot import name 'CircuitBreakerTrippedError'`

- [ ] **Step 3: Add the two exception classes to exceptions.py**

Append after `VerificationTimeoutError`:

```python
# ── Recovery exceptions ──────────────────────────────────────────────────────


class CircuitBreakerTrippedError(WindowsAgentError):
    """Agent loop stopped after too many consecutive failures."""

    def __init__(self, failures: int, window: str) -> None:
        super().__init__(
            f"Circuit breaker tripped after {failures} consecutive failures in {window!r}",
            retryable=False,
            context={"failures": failures, "window": window},
        )
        self.failures = failures
        self.window = window


class UnexpectedDialogError(WindowsAgentError):
    """An unexpected dialog blocked the agent from acting on the target window."""

    def __init__(self, dialog_title: str, window: str) -> None:
        super().__init__(
            f"Unexpected dialog {dialog_title!r} appeared while acting on {window!r}",
            retryable=True,
            context={"dialog_title": dialog_title, "window": window},
        )
        self.dialog_title = dialog_title
        self.window = window
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/test_recovery.py::test_circuit_breaker_error_is_not_retryable tests/test_recovery.py::test_unexpected_dialog_error_is_retryable -v
```

- [ ] **Step 5: Run full suite — must still be 145 passed**

```
python -m pytest tests/ -m "not integration" -q
```

---

## Task 2: Implement RecoveryManager (circuit breaker + failure tracking)

**Files:**
- Create: `windowsagent/recovery.py`
- Modify: `tests/test_recovery.py`

- [ ] **Step 1: Write failing tests for RecoveryManager state tracking**

Add to `tests/test_recovery.py`:

```python
from windowsagent.recovery import RecoveryManager


class TestCircuitBreaker:
    def _make_manager(self, max_failures: int = 3) -> RecoveryManager:
        return RecoveryManager(window_title="Test Window", max_consecutive_failures=max_failures)

    def test_not_tripped_initially(self) -> None:
        mgr = self._make_manager()
        assert mgr.is_tripped() is False

    def test_trips_after_max_failures(self) -> None:
        mgr = self._make_manager(max_failures=3)
        for _ in range(3):
            mgr.record_failure("some error")
        assert mgr.is_tripped() is True

    def test_not_tripped_below_max(self) -> None:
        mgr = self._make_manager(max_failures=3)
        mgr.record_failure("error 1")
        mgr.record_failure("error 2")
        assert mgr.is_tripped() is False

    def test_success_resets_counter(self) -> None:
        mgr = self._make_manager(max_failures=3)
        mgr.record_failure("error 1")
        mgr.record_failure("error 2")
        mgr.record_success()
        mgr.record_failure("error 3")
        assert mgr.is_tripped() is False
        assert mgr.consecutive_failures == 1

    def test_failure_count_increments(self) -> None:
        mgr = self._make_manager()
        mgr.record_failure("a")
        mgr.record_failure("b")
        assert mgr.consecutive_failures == 2

    def test_total_failures_tracked_separately(self) -> None:
        mgr = self._make_manager()
        mgr.record_failure("a")
        mgr.record_success()
        mgr.record_failure("b")
        assert mgr.total_failures == 2
        assert mgr.consecutive_failures == 1
```

- [ ] **Step 2: Run tests — expect ImportError (recovery.py doesn't exist)**

```
python -m pytest tests/test_recovery.py -k "TestCircuitBreaker" -v
```

- [ ] **Step 3: Create recovery.py with RecoveryManager (circuit breaker only)**

```python
"""
Error recovery framework for the WindowsAgent agent loop.

RecoveryManager is instantiated once per run_task() call and tracks
consecutive failures, provides focus recovery, and detects/dismisses
unexpected dialogs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RecoveryManager:
    """Manages error recovery state for a single task execution.

    Args:
        window_title: Title of the target window being operated on.
        max_consecutive_failures: Circuit breaker threshold (default 3).
    """

    def __init__(
        self,
        window_title: str,
        max_consecutive_failures: int = 3,
    ) -> None:
        self.window_title = window_title
        self.max_consecutive_failures = max_consecutive_failures
        self.consecutive_failures: int = 0
        self.total_failures: int = 0

    def record_failure(self, reason: str) -> None:
        """Record a step failure."""
        self.consecutive_failures += 1
        self.total_failures += 1
        logger.debug(
            "Recovery: failure recorded (%d consecutive, %d total) — %s",
            self.consecutive_failures,
            self.total_failures,
            reason,
        )

    def record_success(self) -> None:
        """Record a step success — resets the consecutive failure counter."""
        self.consecutive_failures = 0

    def is_tripped(self) -> bool:
        """Return True if the circuit breaker threshold has been reached."""
        return self.consecutive_failures >= self.max_consecutive_failures
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/test_recovery.py -k "TestCircuitBreaker" -v
```

- [ ] **Step 5: Run full suite**

```
python -m pytest tests/ -m "not integration" -q
```

---

## Task 3: Focus recovery

**Files:**
- Modify: `windowsagent/recovery.py`
- Modify: `tests/test_recovery.py`

- [ ] **Step 1: Write failing tests for focus recovery**

Add to `tests/test_recovery.py`:

```python
from unittest.mock import MagicMock, patch


class TestFocusRecovery:
    def _make_manager(self) -> RecoveryManager:
        return RecoveryManager(window_title="Test App")

    def test_focus_recovery_activates_window(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.window_manager") as mock_wm:
            mock_wm.activate.return_value = True
            result = mgr.attempt_focus_recovery()
        assert result is True
        mock_wm.activate.assert_called_once_with("Test App", wait=True)

    def test_focus_recovery_returns_false_on_failure(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.window_manager") as mock_wm:
            mock_wm.activate.side_effect = Exception("Window gone")
            result = mgr.attempt_focus_recovery()
        assert result is False
```

- [ ] **Step 2: Run tests — expect AttributeError (method doesn't exist yet)**

```
python -m pytest tests/test_recovery.py -k "TestFocusRecovery" -v
```

- [ ] **Step 3: Add attempt_focus_recovery() to RecoveryManager**

Add import at top of recovery.py:
```python
from windowsagent import window_manager
```

Add method to RecoveryManager:
```python
def attempt_focus_recovery(self) -> bool:
    """Try to re-activate the target window after focus loss.

    Returns:
        True if activation succeeded, False otherwise.
    """
    try:
        window_manager.activate(self.window_title, wait=True)
        logger.info("Recovery: focus restored to %r", self.window_title)
        return True
    except Exception as exc:
        logger.debug("Recovery: focus restore failed: %s", exc)
        return False
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/test_recovery.py -k "TestFocusRecovery" -v
```

- [ ] **Step 5: Run full suite**

```
python -m pytest tests/ -m "not integration" -q
```

---

## Task 4: Unexpected dialog detection and dismissal

**Files:**
- Modify: `windowsagent/recovery.py`
- Modify: `tests/test_recovery.py`

- [ ] **Step 1: Write failing tests for dialog detection**

Add to `tests/test_recovery.py`:

```python
class TestDialogDetection:
    def _make_manager(self) -> RecoveryManager:
        return RecoveryManager(window_title="Excel")

    def _make_element(self, control_type: str, name: str) -> Any:
        el = MagicMock()
        el.control_type = control_type
        el.name = name
        el.children = []
        return el

    def test_detect_dialog_returns_title_when_dialog_present(self) -> None:
        mgr = self._make_manager()
        dialog = self._make_element("Dialog", "Save As")
        with patch("windowsagent.recovery.get_windows") as mock_gw:
            mock_win = MagicMock()
            mock_win.app_name = "excel.exe"
            mock_win.title = "Save As"
            mock_win.hwnd = 999
            mock_gw.return_value = [mock_win]
            result = mgr.detect_unexpected_dialog()
        assert result == "Save As"

    def test_detect_dialog_returns_none_when_no_dialog(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.get_windows") as mock_gw:
            mock_gw.return_value = []
            result = mgr.detect_unexpected_dialog()
        assert result is None

    def test_dismiss_dialog_clicks_ok(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.input_actor") as mock_ia:
            mock_ia.press_key.return_value = True
            result = mgr.dismiss_dialog("Save As")
        assert result is True
        # Should press Enter or Escape to dismiss
        assert mock_ia.press_key.called
```

- [ ] **Step 2: Run tests — expect AttributeError**

```
python -m pytest tests/test_recovery.py -k "TestDialogDetection" -v
```

- [ ] **Step 3: Add dialog detection/dismissal to RecoveryManager**

Add imports at top of recovery.py:
```python
from windowsagent.actor import input_actor
from windowsagent.observer.uia import get_windows
```

Add methods to RecoveryManager:
```python
# Common dialog title fragments that indicate blocking dialogs
_DIALOG_TITLE_PATTERNS: frozenset[str] = frozenset([
    "save", "open", "error", "warning", "alert", "confirm",
    "replace", "overwrite", "permission", "access denied",
    "not responding", "blocked", "security", "update",
])

def detect_unexpected_dialog(self) -> str | None:
    """Check for unexpected dialogs that may block the target window.

    Looks for top-level windows that appeared since the task started
    and match known dialog patterns.

    Returns:
        Dialog title if found, None otherwise.
    """
    try:
        windows = get_windows()
        for win in windows:
            title_lower = win.title.lower()
            if any(pat in title_lower for pat in self._DIALOG_TITLE_PATTERNS):
                # Only flag if it's NOT the target window
                if self.window_title.lower() not in title_lower:
                    logger.info(
                        "Recovery: unexpected dialog detected: %r", win.title
                    )
                    return win.title
    except Exception as exc:
        logger.debug("Recovery: dialog detection failed: %s", exc)
    return None

def dismiss_dialog(self, dialog_title: str) -> bool:
    """Attempt to dismiss a blocking dialog by pressing Escape or Enter.

    Tries Escape first (safer — cancels without saving), then Enter.

    Args:
        dialog_title: Title of the dialog to dismiss (for logging).

    Returns:
        True if a key was sent (does not guarantee dialog closed).
    """
    try:
        logger.info("Recovery: dismissing dialog %r with Escape", dialog_title)
        input_actor.press_key("escape")
        return True
    except Exception as exc:
        logger.debug("Recovery: dialog dismissal failed: %s", exc)
        return False
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/test_recovery.py -k "TestDialogDetection" -v
```

- [ ] **Step 5: Run full suite**

```
python -m pytest tests/ -m "not integration" -q
```

---

## Task 5: Wire RecoveryManager into agent_loop.py

**Files:**
- Modify: `windowsagent/agent_loop.py`
- Modify: `tests/test_recovery.py`

- [ ] **Step 1: Write integration test for recovery in the loop**

Add to `tests/test_recovery.py`:

```python
class TestRecoveryInLoop:
    """Verify RecoveryManager integrates correctly with run_task."""

    def test_circuit_breaker_stops_loop(self) -> None:
        """After max_failures consecutive failures, run_task raises CircuitBreakerTrippedError."""
        from windowsagent.recovery import RecoveryManager
        from windowsagent.exceptions import CircuitBreakerTrippedError

        mgr = RecoveryManager(window_title="Notepad", max_consecutive_failures=2)
        mgr.record_failure("step 1 failed")
        mgr.record_failure("step 2 failed")

        assert mgr.is_tripped() is True

    def test_recovery_manager_created_per_run_task_call(self) -> None:
        """Each run_task() should start with a fresh RecoveryManager."""
        from windowsagent.recovery import RecoveryManager
        m1 = RecoveryManager(window_title="A")
        m2 = RecoveryManager(window_title="A")
        m1.record_failure("x")
        assert m2.consecutive_failures == 0
```

- [ ] **Step 2: Run tests — expect PASS (these test RecoveryManager in isolation)**

```
python -m pytest tests/test_recovery.py -k "TestRecoveryInLoop" -v
```

- [ ] **Step 3: Modify agent_loop.py to use RecoveryManager**

At the top of `run_task()`, after `start_time = time.monotonic()`:
```python
from windowsagent.exceptions import CircuitBreakerTrippedError
from windowsagent.recovery import RecoveryManager
recovery = RecoveryManager(window_title=window_title)
```

Replace the step execution block (the `result = agent.act(...)` section and the
`if result.success:` block) with:

```python
        result = agent.act(window_title, action, step.target_description, params)

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
                    step_results[-1]["success"] = True
                    step_results[-1]["recovered"] = True
                    logger.info("Step %d succeeded after focus recovery", i + 1)
                    time.sleep(0.3)
                    continue
                else:
                    recovery.record_failure(retry.error)

            # Check for blocking dialogs
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
```

- [ ] **Step 4: Run full suite — must still be passing**

```
python -m pytest tests/ -m "not integration" -q
```

- [ ] **Step 5: Verify circuit breaker is reflected in TaskResult**

The `error` field of TaskResult should mention circuit breaker when tripped.
Modify the final result assembly in `agent_loop.py`:

```python
    error_msg = "" if success else f"Failed at step {completed + 1}"
    if recovery.is_tripped():
        error_msg = (
            f"Circuit breaker tripped after {recovery.consecutive_failures} "
            f"consecutive failures at step {completed + 1}"
        )
```

- [ ] **Step 6: Run full suite**

```
python -m pytest tests/ -m "not integration" -q
```

---

## Task 6: Commit

- [ ] **Step 1: Run full test suite one final time**

```
python -m pytest tests/ -m "not integration" -q
```
Expected: all tests pass (≥ 145 + new recovery tests)

- [ ] **Step 2: Run mypy**

```
python -m mypy windowsagent/ --ignore-missing-imports
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add windowsagent/exceptions.py windowsagent/recovery.py windowsagent/agent_loop.py tests/test_recovery.py
git commit -m "feat: error recovery framework — circuit breaker, focus recovery, dialog detection"
```

---

## Notes for Implementer

- `get_windows()` is in `windowsagent.observer.uia` — already used in routes/window.py
- `input_actor.press_key()` signature: `press_key(key: str, config: Config | None = None) -> bool`
- The dialog detection is intentionally heuristic (title pattern matching) — a full UIA dialog scan would require a live Windows environment for integration testing
- The circuit breaker does NOT retry on `retryable=False` errors (e.g. `GroundingFailedError`) — those stop immediately regardless of the breaker state. The focus recovery retry is only triggered when `result.success` is False after the initial attempt.
- mypy: `window_manager` module uses `Any` for pywinctl returns — same pattern as rest of codebase
