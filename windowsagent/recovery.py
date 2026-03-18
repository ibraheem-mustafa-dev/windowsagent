"""
Error recovery framework for the WindowsAgent agent loop.

RecoveryManager is instantiated once per run_task() call and tracks
consecutive failures, provides focus recovery, and detects/dismisses
unexpected dialogs that block task execution.

Three recovery mechanisms:
1. Circuit breaker  — stops the loop after N consecutive failures
2. Focus recovery   — re-activates the target window on focus loss
3. Dialog detection — finds and dismisses unexpected blocking dialogs
"""

from __future__ import annotations

import logging

from windowsagent import window_manager
from windowsagent.actor import input_actor
from windowsagent.observer.uia import get_windows

logger = logging.getLogger(__name__)

# Common dialog title fragments that indicate blocking system dialogs
_DIALOG_TITLE_PATTERNS: frozenset[str] = frozenset([
    "save", "open", "error", "warning", "alert", "confirm",
    "replace", "overwrite", "permission", "access denied",
    "not responding", "blocked", "security", "update",
])


class RecoveryManager:
    """Manages error recovery state for a single task execution.

    Instantiate once per run_task() call. Not thread-safe — single-threaded
    agent loop only.

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

    # ── Circuit breaker ───────────────────────────────────────────────────────

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

    # ── Focus recovery ────────────────────────────────────────────────────────

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

    # ── Dialog detection and dismissal ────────────────────────────────────────

    def detect_unexpected_dialog(self) -> str | None:
        """Check for unexpected dialogs that may block the target window.

        Looks for top-level windows whose titles match known dialog patterns
        and are NOT the target window itself.

        Returns:
            Dialog title if found, None otherwise.
        """
        try:
            windows = get_windows()
            for win in windows:
                title_lower = win.title.lower()
                if any(pat in title_lower for pat in _DIALOG_TITLE_PATTERNS):
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
        """Attempt to dismiss a blocking dialog by pressing Escape.

        Escape is the safest dismissal key — cancels without saving state.

        Args:
            dialog_title: Title of the dialog to dismiss (for logging).

        Returns:
            True if the key was sent (does not guarantee dialog closed).
        """
        try:
            logger.info("Recovery: dismissing dialog %r with Escape", dialog_title)
            input_actor.press_key("escape")
            return True
        except Exception as exc:
            logger.debug("Recovery: dialog dismissal failed: %s", exc)
            return False
