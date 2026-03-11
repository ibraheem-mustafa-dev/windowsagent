"""
Base app profile — defines the interface every app profile must implement.

App profiles encapsulate app-specific quirks and provide consistent behaviour
for the agent loop. The agent selects the best matching profile based on
process name and window title, then calls profile methods to customise how
actions are executed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.uia import UIAElement, WindowInfo


class BaseAppProfile(ABC):
    """Abstract base class for all app-specific profiles.

    Subclasses override only the methods where the app needs special handling.
    The defaults provide sensible generic behaviour.

    Class attributes:
        app_names: List of process names this profile handles (lowercase).
        window_titles: List of partial window title strings to match.
        known_elements: Maps natural-language element descriptions (lowercase) to their
            verified UIA Name property strings. Used by the grounder as a fast path —
            if a match is found here, the fuzzy tree scan is skipped and the result is
            returned with high confidence (0.95). Descriptions should cover common
            phrasings, e.g. {"address bar": "Address and search bar"}.
        shortcuts: Maps action names to key combos for the action executor.
            Keys are lowercase snake_case; values are comma-separated key names
            compatible with win32 keybd_event (e.g. "ctrl,l").
    """

    app_names: ClassVar[list[str]] = []
    window_titles: ClassVar[list[str]] = []
    known_elements: ClassVar[dict[str, str]] = {}   # description → UIA Name
    shortcuts: ClassVar[dict[str, str]] = {}         # action name → "ctrl,x" key combo

    def __init__(self, config: Config) -> None:
        """Initialise the profile with the current configuration."""
        self.config = config

    @abstractmethod
    def is_match(self, window_info: WindowInfo) -> bool:
        """Return True if this profile handles the given window.

        Args:
            window_info: Information about the candidate window.

        Returns:
            True if this profile should be used for the window.
        """
        ...

    def on_before_act(  # noqa: B027
        self,
        action: str,
        element: UIAElement | None,
    ) -> None:
        """Called immediately before executing any action.

        Override to implement pre-action setup, such as ensuring a panel has
        focus before interacting with it (e.g. Outlook reading pane prevention).

        Args:
            action: Action type string (e.g. "click", "type", "scroll").
            element: Target element, or None for coordinate-based actions.
        """

    def on_after_act(  # noqa: B027
        self,
        action: str,
        element: UIAElement | None,
        success: bool,
    ) -> None:
        """Called immediately after executing any action.

        Override to implement post-action cleanup, such as waiting for a
        specific UI state before continuing.

        Args:
            action: Action type string.
            element: Target element, or None.
            success: Whether the action reported success.
        """

    def get_scroll_strategy(self) -> Literal["scroll_pattern", "keyboard", "webview2"]:
        """Return the preferred scroll strategy for this app.

        Returns:
            - "scroll_pattern": Use UIA ScrollPattern (native apps, standard UWP)
            - "keyboard": Use Page Up/Down keys (some custom controls)
            - "webview2": Click in content area then use keys (WebView2 apps)
        """
        return "scroll_pattern"

    def requires_focus_restore(self) -> bool:
        """Return True if this app tends to steal focus unexpectedly.

        When True, the agent loop will re-verify that the target panel still
        has focus after each action (e.g. Outlook's reading pane steals focus
        when clicking an email in the list).

        Returns:
            True if focus should be re-validated after each action.
        """
        return False

    def get_text_input_strategy(self) -> Literal["value_pattern", "keyboard", "clipboard"]:
        """Return preferred text input strategy for this app.

        Returns:
            - "value_pattern": Use ValuePattern.SetValue (fastest, most reliable)
            - "keyboard": Use keyboard simulation (for apps that intercept clipboard)
            - "clipboard": Always use clipboard paste (for very long text)
        """
        return "value_pattern"

    def get_element_hint(self, description: str) -> str | None:
        """Return the known UIA Name for an element description, or None.

        Case-insensitive lookup against known_elements. Used by the grounder
        to skip the fuzzy tree scan for well-understood apps.

        Args:
            description: Natural language element description (e.g. "address bar").

        Returns:
            The exact UIA Name string if known, or None to fall back to tree scan.
        """
        key = description.strip().lower()
        # Exact match
        if key in self.known_elements:
            return self.known_elements[key]
        # Substring match — e.g. "the address bar" → "address bar"
        for known_key, uia_name in self.known_elements.items():
            if known_key in key or key in known_key:
                return uia_name
        return None

    def get_shortcut(self, action: str) -> str | None:
        """Return the key combo for a named action, or None if not defined.

        Args:
            action: Action name (e.g. "new_tab", "address_bar", "find").

        Returns:
            Key combo string (e.g. "ctrl,t") or None.
        """
        return self.shortcuts.get(action.lower().replace(" ", "_"))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
