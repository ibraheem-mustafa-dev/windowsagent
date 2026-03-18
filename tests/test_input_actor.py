"""
Tests for actor/input_actor.py — coordinate-based input via pyautogui.

All tests mock pyautogui to avoid real mouse/keyboard actions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from windowsagent.exceptions import ActionFailedError


# ── _get_pyautogui ───────────────────────────────────────────────────────────


class TestGetPyautogui:
    def test_returns_pyautogui_with_safety_settings(self) -> None:
        from windowsagent.actor.input_actor import _get_pyautogui

        pag = _get_pyautogui()
        assert pag.FAILSAFE is True
        assert pag.PAUSE == 0.02

    def test_raises_action_failed_when_not_installed(self) -> None:
        with patch.dict("sys.modules", {"pyautogui": None}):
            # Need to reimport to trigger the ImportError
            import importlib
            import windowsagent.actor.input_actor as mod

            importlib.reload(mod)
            with pytest.raises(ActionFailedError, match="pyautogui not installed"):
                mod._get_pyautogui()

            # Restore
            importlib.reload(mod)


# ── _scale_coords ────────────────────────────────────────────────────────────


class TestScaleCoords:
    def test_scales_by_dpi_factor(self) -> None:
        from windowsagent.actor.input_actor import _scale_coords

        with patch("windowsagent.observer.screenshot.get_dpi_scale", return_value=1.5):
            px, py = _scale_coords(100, 200, None)
            assert px == 150
            assert py == 300

    def test_returns_original_on_error(self) -> None:
        from windowsagent.actor.input_actor import _scale_coords

        with patch(
            "windowsagent.observer.screenshot.get_dpi_scale",
            side_effect=RuntimeError("no display"),
        ):
            px, py = _scale_coords(100, 200, None)
            assert px == 100
            assert py == 200


# ── click_at ─────────────────────────────────────────────────────────────────


class TestClickAt:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_click_at_calls_pyautogui(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import click_at

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = click_at(100, 200, button="left")
        assert result is True
        mock_pag_instance.click.assert_called_once()

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_click_at_right_button(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import click_at

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = click_at(100, 200, button="right")
        assert result is True
        mock_pag_instance.click.assert_called_once_with(
            100, 200, button="right", duration=0.08
        )

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_click_at_raises_on_failure(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import click_at

        mock_pag_instance = MagicMock()
        mock_pag_instance.click.side_effect = RuntimeError("display error")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Click at"):
            click_at(50, 50)


# ── double_click_at ──────────────────────────────────────────────────────────


class TestDoubleClickAt:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_double_click_calls_pyautogui(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import double_click_at

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = double_click_at(100, 200)
        assert result is True
        mock_pag_instance.doubleClick.assert_called_once()

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_double_click_raises_on_failure(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import double_click_at

        mock_pag_instance = MagicMock()
        mock_pag_instance.doubleClick.side_effect = RuntimeError("fail")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Double-click"):
            double_click_at(50, 50)


# ── right_click_at ───────────────────────────────────────────────────────────


class TestRightClickAt:
    @patch("windowsagent.actor.input_actor.click_at")
    def test_delegates_to_click_at_with_right(self, mock_click: MagicMock) -> None:
        from windowsagent.actor.input_actor import right_click_at

        mock_click.return_value = True
        result = right_click_at(10, 20)
        assert result is True
        mock_click.assert_called_once_with(10, 20, button="right", config=None)


# ── type_text ────────────────────────────────────────────────────────────────


class TestTypeText:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_type_ascii_text(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import type_text

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = type_text("hello world")
        assert result is True
        mock_pag_instance.write.assert_called_once_with("hello world", interval=0.02)

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_type_text_raises_on_failure(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import type_text

        mock_pag_instance = MagicMock()
        mock_pag_instance.write.side_effect = RuntimeError("keyboard locked")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Keyboard typing failed"):
            type_text("test")


# ── press_key ────────────────────────────────────────────────────────────────


class TestPressKey:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_press_key_success(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import press_key

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = press_key("enter")
        assert result is True
        mock_pag_instance.press.assert_called_once_with("enter")

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_press_key_raises_on_failure(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import press_key

        mock_pag_instance = MagicMock()
        mock_pag_instance.press.side_effect = RuntimeError("fail")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Key press"):
            press_key("escape")


# ── hotkey ───────────────────────────────────────────────────────────────────


class TestHotkey:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_hotkey_success(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import hotkey

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = hotkey("ctrl", "s")
        assert result is True
        mock_pag_instance.hotkey.assert_called_once_with("ctrl", "s")

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    def test_hotkey_raises_on_failure(self, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import hotkey

        mock_pag_instance = MagicMock()
        mock_pag_instance.hotkey.side_effect = RuntimeError("fail")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Hotkey"):
            hotkey("ctrl", "alt", "delete")


# ── scroll_at ────────────────────────────────────────────────────────────────


class TestScrollAt:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_scroll_down(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import scroll_at

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = scroll_at(100, 200, direction="down", amount=3)
        assert result is True
        mock_pag_instance.scroll.assert_called_once_with(-3, x=100, y=200)

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_scroll_up(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import scroll_at

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = scroll_at(100, 200, direction="up", amount=5)
        assert result is True
        mock_pag_instance.scroll.assert_called_once_with(5, x=100, y=200)

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_scroll_raises_on_failure(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import scroll_at

        mock_pag_instance = MagicMock()
        mock_pag_instance.scroll.side_effect = RuntimeError("fail")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Scroll at"):
            scroll_at(50, 50, direction="down", amount=1)


# ── move_to ──────────────────────────────────────────────────────────────────


class TestMoveTo:
    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_move_to_success(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import move_to

        mock_pag_instance = MagicMock()
        mock_pag.return_value = mock_pag_instance

        result = move_to(100, 200)
        assert result is True
        mock_pag_instance.moveTo.assert_called_once()

    @patch("windowsagent.actor.input_actor._get_pyautogui")
    @patch("windowsagent.actor.input_actor._scale_coords", return_value=(100, 200))
    def test_move_to_raises_on_failure(self, mock_scale: MagicMock, mock_pag: MagicMock) -> None:
        from windowsagent.actor.input_actor import move_to

        mock_pag_instance = MagicMock()
        mock_pag_instance.moveTo.side_effect = RuntimeError("fail")
        mock_pag.return_value = mock_pag_instance

        with pytest.raises(ActionFailedError, match="Mouse move"):
            move_to(50, 50)
