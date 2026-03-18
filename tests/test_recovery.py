"""Tests for the error recovery framework."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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


# ── RecoveryManager — circuit breaker ─────────────────────────────────────────


class TestCircuitBreaker:
    def _make_manager(self, max_failures: int = 3) -> object:
        from windowsagent.recovery import RecoveryManager
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


# ── RecoveryManager — focus recovery ─────────────────────────────────────────


class TestFocusRecovery:
    def _make_manager(self) -> object:
        from windowsagent.recovery import RecoveryManager
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


# ── RecoveryManager — dialog detection ───────────────────────────────────────


class TestDialogDetection:
    def _make_manager(self) -> object:
        from windowsagent.recovery import RecoveryManager
        return RecoveryManager(window_title="Excel")

    def _make_window_info(self, app_name: str, title: str) -> Any:
        wi = MagicMock()
        wi.app_name = app_name
        wi.title = title
        wi.hwnd = 999
        return wi

    def test_detect_dialog_returns_title_when_dialog_present(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.get_windows") as mock_gw:
            mock_gw.return_value = [self._make_window_info("excel.exe", "Save As")]
            result = mgr.detect_unexpected_dialog()
        assert result == "Save As"

    def test_detect_dialog_returns_none_when_no_dialog(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.get_windows") as mock_gw:
            mock_gw.return_value = []
            result = mgr.detect_unexpected_dialog()
        assert result is None

    def test_detect_dialog_ignores_target_window_title(self) -> None:
        # A window whose title contains the target window name is not a dialog
        mgr = self._make_manager()
        with patch("windowsagent.recovery.get_windows") as mock_gw:
            # "Excel" is in "Book1 - Excel" — should be ignored
            mock_gw.return_value = [self._make_window_info("excel.exe", "Book1 - Excel")]
            result = mgr.detect_unexpected_dialog()
        assert result is None

    def test_dismiss_dialog_presses_escape(self) -> None:
        mgr = self._make_manager()
        with patch("windowsagent.recovery.input_actor") as mock_ia:
            mock_ia.press_key.return_value = True
            result = mgr.dismiss_dialog("Save As")
        assert result is True
        mock_ia.press_key.assert_called_once_with("escape")


# ── Integration — RecoveryManager in isolation ────────────────────────────────


class TestRecoveryInLoop:
    def test_circuit_breaker_stops_loop(self) -> None:
        from windowsagent.recovery import RecoveryManager

        mgr = RecoveryManager(window_title="Notepad", max_consecutive_failures=2)
        mgr.record_failure("step 1 failed")
        mgr.record_failure("step 2 failed")
        assert mgr.is_tripped() is True

    def test_recovery_manager_created_per_run_task_call(self) -> None:
        from windowsagent.recovery import RecoveryManager
        m1 = RecoveryManager(window_title="A")
        m2 = RecoveryManager(window_title="A")
        m1.record_failure("x")
        assert m2.consecutive_failures == 0
