"""
Apps module — application-specific profiles for known Windows apps.

Each profile encapsulates app-specific element names, keyboard shortcuts,
input/scroll strategies, and known quirks. Unknown apps fall back to
GenericAppProfile.

Profiles registered here are matched against the target window's process
name and title. The first matching profile is used.

Built-in profiles:
- ChromeProfile, EdgeProfile, ExcelProfile, VSCodeProfile, TeamsProfile,
  PowerShellProfile, WhatsAppWebProfile, NotepadProfile, OutlookProfile,
  FileExplorerProfile, WebView2Profile, GenericAppProfile

Community profiles are auto-discovered from apps/community/.
"""

import logging

from windowsagent.apps.base import BaseAppProfile
from windowsagent.apps.chrome import ChromeProfile
from windowsagent.apps.edge import EdgeProfile
from windowsagent.apps.excel import ExcelProfile
from windowsagent.apps.file_explorer import FileExplorerProfile
from windowsagent.apps.generic import GenericAppProfile
from windowsagent.apps.notepad import NotepadProfile
from windowsagent.apps.outlook import OutlookProfile
from windowsagent.apps.powershell import PowerShellProfile
from windowsagent.apps.teams import TeamsProfile
from windowsagent.apps.vscode import VSCodeProfile
from windowsagent.apps.webview2 import WebView2Profile
from windowsagent.apps.whatsapp import WhatsAppWebProfile

_logger = logging.getLogger(__name__)

# Ordered list of profiles to check. More specific profiles must come before
# generic ones. GenericAppProfile must be last.
_PROFILES: list[type[BaseAppProfile]] = [
    # Title-based matches must come before their browser host profiles
    WhatsAppWebProfile,   # 'WhatsApp' in title — checked before Edge/Chrome
    # Process-name-based profiles (specific → generic)
    NotepadProfile,
    FileExplorerProfile,
    ExcelProfile,
    OutlookProfile,
    TeamsProfile,
    VSCodeProfile,
    PowerShellProfile,
    ChromeProfile,
    EdgeProfile,
    WebView2Profile,
]

# Auto-discover community profiles and insert before GenericAppProfile
try:
    from windowsagent.apps.community import discover_profiles
    _community = discover_profiles()
    if _community:
        _PROFILES.extend(_community)
        _logger.info("Loaded %d community profile(s)", len(_community))
except Exception:
    _logger.debug("No community profiles loaded", exc_info=True)

# GenericAppProfile must always be last — it matches everything
_PROFILES.append(GenericAppProfile)


def get_profile(app_name: str, window_title: str) -> BaseAppProfile:
    """Return the best matching app profile for the given app/window.

    Checks profiles in priority order — most specific first. The first
    profile whose is_match() returns True is used. GenericAppProfile
    always matches as the final fallback.

    Args:
        app_name: Process name (e.g. "notepad.exe", "msedge.exe")
        window_title: Window title string

    Returns:
        An initialised app profile instance.
    """
    from windowsagent.config import load_config
    from windowsagent.observer.uia import WindowInfo

    config = load_config()

    # Build a minimal WindowInfo for matching
    dummy = WindowInfo(
        title=window_title,
        app_name=app_name,
        pid=0,
        hwnd=0,
        rect=(0, 0, 0, 0),
        is_visible=True,
        is_enabled=True,
    )

    for profile_cls in _PROFILES:
        profile = profile_cls(config)
        if profile.is_match(dummy):
            return profile

    # Should never reach here — GenericAppProfile always matches
    return GenericAppProfile(config)


__all__ = [
    "BaseAppProfile",
    "ChromeProfile",
    "EdgeProfile",
    "ExcelProfile",
    "FileExplorerProfile",
    "GenericAppProfile",
    "NotepadProfile",
    "OutlookProfile",
    "PowerShellProfile",
    "TeamsProfile",
    "VSCodeProfile",
    "WebView2Profile",
    "WhatsAppWebProfile",
    "get_profile",
]
