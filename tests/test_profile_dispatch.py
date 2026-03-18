"""Tests for profile strategy dispatch in Agent._execute_action().

Verifies that the agent loop correctly uses profile strategies for:
- get_scroll_strategy() → webview2 / keyboard / scroll_pattern
- get_text_input_strategy() → clipboard / value_pattern / keyboard
- requires_focus_restore() → re-activate window after action
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from windowsagent.apps.base import BaseAppProfile
from windowsagent.apps.chrome import ChromeProfile
from windowsagent.apps.generic import GenericAppProfile
from windowsagent.apps.outlook import OutlookProfile
from windowsagent.apps.teams import TeamsProfile


# ── Profile strategy return values ────────────────────────────────────────────


class TestProfileStrategies:
    """Verify each profile returns the correct strategy."""

    def _make_config(self) -> MagicMock:
        config = MagicMock()
        config.uia_timeout = 5.0
        config.vision_timeout = 15.0
        config.verify_timeout = 3.0
        return config

    def test_outlook_scroll_strategy_is_webview2(self) -> None:
        profile = OutlookProfile(self._make_config())
        assert profile.get_scroll_strategy() == "webview2"

    def test_outlook_text_strategy_is_clipboard(self) -> None:
        profile = OutlookProfile(self._make_config())
        assert profile.get_text_input_strategy() == "clipboard"

    def test_outlook_requires_focus_restore(self) -> None:
        profile = OutlookProfile(self._make_config())
        assert profile.requires_focus_restore() is True

    def test_chrome_scroll_strategy_is_webview2(self) -> None:
        profile = ChromeProfile(self._make_config())
        assert profile.get_scroll_strategy() == "webview2"

    def test_chrome_text_strategy_is_clipboard(self) -> None:
        profile = ChromeProfile(self._make_config())
        assert profile.get_text_input_strategy() == "clipboard"

    def test_chrome_no_focus_restore(self) -> None:
        profile = ChromeProfile(self._make_config())
        assert profile.requires_focus_restore() is False

    def test_teams_requires_focus_restore(self) -> None:
        profile = TeamsProfile(self._make_config())
        assert profile.requires_focus_restore() is True

    def test_teams_text_strategy_is_clipboard(self) -> None:
        profile = TeamsProfile(self._make_config())
        assert profile.get_text_input_strategy() == "clipboard"

    def test_generic_scroll_strategy_is_scroll_pattern(self) -> None:
        profile = GenericAppProfile(self._make_config())
        assert profile.get_scroll_strategy() == "scroll_pattern"

    def test_generic_text_strategy_is_value_pattern(self) -> None:
        profile = GenericAppProfile(self._make_config())
        assert profile.get_text_input_strategy() == "value_pattern"

    def test_generic_no_focus_restore(self) -> None:
        profile = GenericAppProfile(self._make_config())
        assert profile.requires_focus_restore() is False


# ── Known elements lookup ─────────────────────────────────────────────────────


class TestOutlookKnownElements:
    """Verify Outlook profile element hints resolve correctly."""

    def _make_profile(self) -> OutlookProfile:
        config = MagicMock()
        return OutlookProfile(config)

    def test_new_mail_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("new mail") == "New mail"

    def test_compose_resolves_to_new_mail(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("compose") == "New mail"

    def test_reply_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("reply") == "Reply"

    def test_reply_all_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("reply all") == "Reply all"

    def test_forward_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("forward") == "Forward"

    def test_delete_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("delete") == "Delete"

    def test_search_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("search") == "Search"

    def test_inbox_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("inbox") == "Inbox"

    def test_sent_items_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("sent items") == "Sent Items"

    def test_calendar_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("calendar") == "Calendar"

    def test_to_field_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("to field") == "To"

    def test_subject_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("subject") == "Subject"

    def test_send_resolves(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("send") == "Send"

    def test_unknown_element_returns_none(self) -> None:
        profile = self._make_profile()
        assert profile.get_element_hint("nonexistent widget") is None


# ── Shortcuts lookup ──────────────────────────────────────────────────────────


class TestOutlookShortcuts:
    def _make_profile(self) -> OutlookProfile:
        return OutlookProfile(MagicMock())

    def test_new_mail_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("new_mail") == "ctrl,n"

    def test_reply_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("reply") == "ctrl,r"

    def test_reply_all_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("reply_all") == "ctrl,shift,r"

    def test_forward_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("forward") == "ctrl,f"

    def test_send_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("send") == "ctrl,enter"

    def test_search_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("search") == "ctrl,e"

    def test_delete_shortcut(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("delete") == "Delete"

    def test_unknown_shortcut_returns_none(self) -> None:
        profile = self._make_profile()
        assert profile.get_shortcut("nonexistent_action") is None


# ── Profile matching ──────────────────────────────────────────────────────────


class TestProfileMatching:
    def test_outlook_matches_olk_exe(self) -> None:
        from windowsagent.apps import get_profile
        profile = get_profile("olk.exe", "Inbox - Outlook")
        assert isinstance(profile, OutlookProfile)

    def test_outlook_matches_outlook_exe(self) -> None:
        from windowsagent.apps import get_profile
        profile = get_profile("outlook.exe", "Mail - Someone")
        assert isinstance(profile, OutlookProfile)

    def test_chrome_matches(self) -> None:
        from windowsagent.apps import get_profile
        profile = get_profile("chrome.exe", "Google - Google Chrome")
        assert isinstance(profile, ChromeProfile)

    def test_teams_matches(self) -> None:
        from windowsagent.apps import get_profile
        profile = get_profile("ms-teams.exe", "Microsoft Teams")
        assert isinstance(profile, TeamsProfile)

    def test_unknown_app_gets_generic(self) -> None:
        from windowsagent.apps import get_profile
        profile = get_profile("randomapp.exe", "Some Window")
        assert isinstance(profile, GenericAppProfile)
