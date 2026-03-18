"""
Community app profile template.

Copy this file and rename it to match your application (e.g. spotify.py).
Fill in the class attributes and implement is_match(). See the docstrings
below for guidance on each field.

Refer to windowsagent/apps/base.py for the full BaseAppProfile interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class TemplateProfile(BaseAppProfile):
    """App profile for [Your Application Name].

    Replace this docstring with a brief description of the app and any
    automation quirks worth noting.
    """

    # Process names that identify this app (lowercase).
    # Find yours: Task Manager → Details tab → look for the .exe name.
    app_names: ClassVar[list[str]] = ["your_app.exe"]

    # Partial window title strings to match.
    # The grounder checks if any of these appear in the window title.
    window_titles: ClassVar[list[str]] = ["Your App"]

    # Maps natural-language descriptions to verified UIA Name strings.
    # To find UIA names: run `windowsagent observe --window "Your App" --json-output`
    # and look at the "name" field of each element in the UIA tree.
    #
    # Tips:
    # - Include common phrasings (e.g. "search" and "search bar" both → same element)
    # - Keys must be lowercase
    # - Values must match the exact UIA Name string (case-sensitive)
    known_elements: ClassVar[dict[str, str]] = {
        # "description": "Exact UIA Name",
    }

    # Maps action names to keyboard shortcuts.
    # Keys: lowercase snake_case action names
    # Values: comma-separated key names (e.g. "ctrl,s", "alt,f4")
    shortcuts: ClassVar[dict[str, str]] = {
        # "action_name": "key,combo",
    }

    def is_match(self, window_info: WindowInfo) -> bool:
        """Return True if this profile handles the given window.

        Typical implementation checks process name and/or window title.
        """
        return (
            window_info.app_name.lower() in self.app_names
            or any(t.lower() in window_info.title.lower() for t in self.window_titles)
        )

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        """Return the preferred scroll strategy.

        - "scroll_pattern": UIA ScrollPattern (native Win32/UWP apps)
        - "keyboard": Page Up/Down keys (some custom controls)
        - "webview2": Click in content then use keys (WebView2/Electron apps)
        """
        return "scroll_pattern"

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        """Return the preferred text input strategy.

        - "value_pattern": UIA ValuePattern.SetValue (fastest, most reliable)
        - "keyboard": Keyboard simulation (for apps that intercept clipboard)
        - "clipboard": Clipboard paste (for special characters or long text)
        """
        return "value_pattern"

    def requires_focus_restore(self) -> bool:
        """Return True if this app steals focus after standard actions."""
        return False
