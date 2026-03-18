"""
Tests for the community profiles auto-discovery system.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestDiscoverProfiles:
    def test_empty_directory_returns_empty(self) -> None:
        from windowsagent.apps.community import discover_profiles

        # With no community .py files (only _template.py which is skipped), returns []
        profiles = discover_profiles()
        assert profiles == []

    def test_skips_underscore_prefixed_modules(self) -> None:
        from windowsagent.apps.community import discover_profiles

        # _template.py starts with underscore, should be skipped
        profiles = discover_profiles()
        assert not any(p.__name__ == "TemplateProfile" for p in profiles)

    def test_discovers_valid_profile(self) -> None:
        import importlib
        import sys
        import types

        from windowsagent.apps.base import BaseAppProfile

        # Create a real module with a profile class
        mod_name = "windowsagent.apps.community.spotify"
        fake_module = types.ModuleType(mod_name)

        class FakeSpotifyProfile(BaseAppProfile):
            app_names = ["spotify.exe"]
            window_titles = ["Spotify"]

            def is_match(self, window_info: object) -> bool:
                return True

        FakeSpotifyProfile.__module__ = mod_name
        fake_module.FakeSpotifyProfile = FakeSpotifyProfile  # type: ignore[attr-defined]

        # Register the fake module so importlib can find it
        sys.modules[mod_name] = fake_module
        try:
            with patch(
                "windowsagent.apps.community.pkgutil.iter_modules",
                return_value=[(None, "spotify", False)],
            ):
                from windowsagent.apps.community import discover_profiles
                profiles = discover_profiles()
        finally:
            del sys.modules[mod_name]

        assert len(profiles) == 1
        assert profiles[0] is FakeSpotifyProfile

    @patch("windowsagent.apps.community.pkgutil.iter_modules")
    @patch("windowsagent.apps.community.importlib.import_module")
    def test_handles_import_error_gracefully(
        self, mock_import: MagicMock, mock_iter: MagicMock,
    ) -> None:
        from windowsagent.apps.community import discover_profiles

        mock_iter.return_value = [(None, "broken_module", False)]
        mock_import.side_effect = ImportError("missing dependency")

        # Should not raise, just log and skip
        profiles = discover_profiles()
        assert profiles == []

    @patch("windowsagent.apps.community.pkgutil.iter_modules")
    @patch("windowsagent.apps.community.importlib.import_module")
    def test_ignores_non_profile_classes(
        self, mock_import: MagicMock, mock_iter: MagicMock,
    ) -> None:
        from windowsagent.apps.community import discover_profiles

        class NotAProfile:
            pass

        mock_iter.return_value = [(None, "misc", False)]
        fake_module = MagicMock()
        fake_module.__name__ = "windowsagent.apps.community.misc"
        mock_import.return_value = fake_module

        with patch("windowsagent.apps.community.inspect.getmembers") as mock_members:
            mock_members.return_value = [("NotAProfile", NotAProfile)]
            profiles = discover_profiles()

        assert profiles == []


class TestProfileRegistration:
    def test_generic_profile_is_last(self) -> None:
        from windowsagent.apps import _PROFILES
        from windowsagent.apps.generic import GenericAppProfile

        assert _PROFILES[-1] is GenericAppProfile

    def test_builtin_profiles_before_generic(self) -> None:
        from windowsagent.apps import _PROFILES
        from windowsagent.apps.generic import GenericAppProfile
        from windowsagent.apps.notepad import NotepadProfile

        notepad_idx = _PROFILES.index(NotepadProfile)
        generic_idx = _PROFILES.index(GenericAppProfile)
        assert notepad_idx < generic_idx

    def test_get_profile_falls_back_to_generic(self) -> None:
        from windowsagent.apps import get_profile
        from windowsagent.apps.generic import GenericAppProfile

        profile = get_profile("unknown_app.exe", "Random Window")
        assert isinstance(profile, GenericAppProfile)
