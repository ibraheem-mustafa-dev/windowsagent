"""Tests for windowsagent.window_manager — pywinctl integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from windowsagent.exceptions import WindowNotFoundError
from windowsagent.window_manager import (
    WindowGeometry,
    activate,
    activate_by_hwnd,
    bring_to_front,
    close,
    find_window,
    find_windows,
    get_all_titles,
    get_geometry,
    is_active,
    is_alive,
    is_maximised,
    is_minimised,
    is_visible,
    maximise,
    minimise,
    move,
    resize,
    restore,
    send_to_back,
)


# ── WindowGeometry tests ──────────────────────────────────────────────────────


class TestWindowGeometry:
    def test_right_and_bottom(self) -> None:
        geom = WindowGeometry(left=100, top=200, width=800, height=600)
        assert geom.right == 900
        assert geom.bottom == 800

    def test_centre(self) -> None:
        geom = WindowGeometry(left=0, top=0, width=1000, height=500)
        assert geom.centre == (500, 250)

    def test_zero_size(self) -> None:
        geom = WindowGeometry(left=50, top=50, width=0, height=0)
        assert geom.right == 50
        assert geom.bottom == 50
        assert geom.centre == (50, 50)


# ── find_windows / find_window tests ──────────────────────────────────────────


class TestFindWindows:
    def test_find_windows_returns_matches(self) -> None:
        mock_win1 = MagicMock()
        mock_win1.title = "Notepad - test.txt"
        mock_win2 = MagicMock()
        mock_win2.title = "Notepad++ Editor"

        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getWindowsWithTitle.return_value = [mock_win1, mock_win2]
            result = find_windows("Notepad")
            assert len(result) == 2

    def test_find_windows_returns_empty(self) -> None:
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getWindowsWithTitle.return_value = []
            result = find_windows("NonexistentWindow")
            assert result == []

    def test_find_window_raises_on_no_match(self) -> None:
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getWindowsWithTitle.return_value = []
            with pytest.raises(WindowNotFoundError):
                find_window("NonexistentWindow")

    def test_find_window_returns_first_match(self) -> None:
        mock_win = MagicMock()
        mock_win.title = "Notepad"
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getWindowsWithTitle.return_value = [mock_win]
            result = find_window("Notepad")
            assert result == mock_win


# ── Window state query tests ──────────────────────────────────────────────────


class TestWindowStateQueries:
    def test_is_alive_true(self) -> None:
        win = MagicMock()
        win.isAlive.return_value = True
        assert is_alive(win) is True

    def test_is_alive_false(self) -> None:
        win = MagicMock()
        win.isAlive.side_effect = Exception("dead")
        assert is_alive(win) is False

    def test_is_active(self) -> None:
        win = MagicMock()
        win.isActive = True
        assert is_active(win) is True

    def test_is_minimised(self) -> None:
        win = MagicMock()
        win.isMinimized = True
        assert is_minimised(win) is True

    def test_is_maximised(self) -> None:
        win = MagicMock()
        win.isMaximized = False
        assert is_maximised(win) is False

    def test_is_visible(self) -> None:
        win = MagicMock()
        win.isVisible = True
        assert is_visible(win) is True


# ── Window action tests ───────────────────────────────────────────────────────


class TestWindowActions:
    def test_activate_normal_window(self) -> None:
        win = MagicMock()
        win.isMinimized = False
        win.activate.return_value = True
        assert activate(win) is True
        win.activate.assert_called_once_with(wait=True)

    def test_activate_minimised_window_restores_first(self) -> None:
        win = MagicMock()
        win.isMinimized = True
        win.restore.return_value = True
        win.activate.return_value = True
        activate(win)
        win.restore.assert_called_once_with(wait=True)
        win.activate.assert_called_once()

    def test_activate_by_title_string(self) -> None:
        mock_win = MagicMock()
        mock_win.isMinimized = False
        mock_win.activate.return_value = True
        with patch("windowsagent.window_manager.find_window", return_value=mock_win):
            result = activate("Notepad")
            assert result is True

    def test_activate_by_hwnd(self) -> None:
        mock_win = MagicMock()
        mock_win.isMinimized = False
        mock_win.getHandle.return_value = 12345
        mock_win.activate.return_value = True
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getAllWindows.return_value = [mock_win]
            result = activate_by_hwnd(12345)
            assert result is True

    def test_activate_by_hwnd_not_found(self) -> None:
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getAllWindows.return_value = []
            result = activate_by_hwnd(99999)
            assert result is False

    def test_minimise(self) -> None:
        win = MagicMock()
        win.minimize.return_value = True
        assert minimise(win) is True
        win.minimize.assert_called_once_with(wait=True)

    def test_maximise(self) -> None:
        win = MagicMock()
        win.maximize.return_value = True
        assert maximise(win) is True

    def test_restore(self) -> None:
        win = MagicMock()
        win.restore.return_value = True
        assert restore(win) is True

    def test_move(self) -> None:
        win = MagicMock()
        win.moveTo.return_value = True
        assert move(win, 100, 200) is True
        win.moveTo.assert_called_once_with(100, 200)

    def test_resize(self) -> None:
        win = MagicMock()
        win.resizeTo.return_value = True
        assert resize(win, 800, 600) is True
        win.resizeTo.assert_called_once_with(800, 600)

    def test_bring_to_front(self) -> None:
        win = MagicMock()
        win.raiseWindow.return_value = True
        assert bring_to_front(win) is True

    def test_send_to_back(self) -> None:
        win = MagicMock()
        win.lowerWindow.return_value = True
        assert send_to_back(win) is True

    def test_close(self) -> None:
        win = MagicMock()
        win.close.return_value = True
        assert close(win) is True


# ── Geometry tests ────────────────────────────────────────────────────────────


class TestGetGeometry:
    def test_get_geometry_from_client_frame(self) -> None:
        win = MagicMock()
        frame = MagicMock()
        frame.left = 100
        frame.top = 200
        frame.right = 900
        frame.bottom = 800
        win.getClientFrame.return_value = frame
        geom = get_geometry(win)
        assert geom.left == 100
        assert geom.top == 200
        assert geom.width == 800
        assert geom.height == 600


# ── get_all_titles test ───────────────────────────────────────────────────────


class TestGetAllTitles:
    def test_returns_titles(self) -> None:
        with patch("windowsagent.window_manager._get_pywinctl") as mock_pwc:
            mock_pwc.return_value.getAllTitles.return_value = ["Notepad", "Chrome"]
            result = get_all_titles()
            assert result == ["Notepad", "Chrome"]


# ── Integration tests (require Windows desktop) ──────────────────────────────


@pytest.mark.integration
class TestWindowManagerIntegration:
    def test_get_all_titles_returns_list(self) -> None:
        titles = get_all_titles()
        assert isinstance(titles, list)
        assert len(titles) > 0

    def test_find_window_finds_desktop(self) -> None:
        # There should always be some window on a Windows desktop
        from windowsagent.window_manager import get_all_windows
        windows = get_all_windows()
        assert len(windows) > 0
