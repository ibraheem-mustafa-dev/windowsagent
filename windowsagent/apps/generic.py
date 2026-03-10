"""
Generic app profile — fallback for any unrecognised application.

Used when no specific profile matches the target window. Implements all
BaseAppProfile methods with sensible defaults using standard UIA patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from windowsagent.apps.base import BaseAppProfile

if TYPE_CHECKING:
    from windowsagent.observer.uia import WindowInfo


class GenericAppProfile(BaseAppProfile):
    """Fallback profile used for all unrecognised Windows applications.

    Uses standard UIA scroll patterns and makes no assumptions about focus
    behaviour. Suitable for most well-behaved Win32 and UWP applications.
    """

    app_names: ClassVar[list[str]] = []
    window_titles: ClassVar[list[str]] = []

    def is_match(self, window_info: WindowInfo) -> bool:
        """Always returns True — this is the catch-all profile."""
        return True
