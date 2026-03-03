"""
Apps module — application-specific profiles for known Windows apps.

Each profile handles quirks and provides a consistent interface for common
operations. Unknown apps fall back to GenericAppProfile.

Available profiles:
- NotepadProfile: Windows Notepad (simple test target)
- FileExplorerProfile: Windows File Explorer
- OutlookProfile: Microsoft Outlook (WebView2-based)
- WebView2Profile: Shared handler for any WebView2 app
- GenericAppProfile: Fallback for unrecognised apps
"""

from windowsagent.apps.base import BaseAppProfile
from windowsagent.apps.file_explorer import FileExplorerProfile
from windowsagent.apps.generic import GenericAppProfile
from windowsagent.apps.notepad import NotepadProfile
from windowsagent.apps.outlook import OutlookProfile
from windowsagent.apps.webview2 import WebView2Profile


def get_profile(app_name: str, window_title: str) -> "BaseAppProfile":
    """Return the best matching app profile for the given app/window.

    Args:
        app_name: Process name (e.g. "notepad.exe")
        window_title: Window title string

    Returns:
        An initialised app profile instance.
    """
    from windowsagent.config import load_config

    config = load_config()
    app_name_lower = app_name.lower()
    title_lower = window_title.lower()

    if "notepad" in app_name_lower or "notepad" in title_lower:
        return NotepadProfile(config)
    if "explorer" in app_name_lower and "file" not in title_lower.replace("file", ""):
        return FileExplorerProfile(config)
    if app_name_lower == "explorer.exe":
        return FileExplorerProfile(config)
    if any(name in app_name_lower for name in ("olk.exe", "outlook")):
        return OutlookProfile(config)

    from windowsagent.apps.webview2 import is_webview2_process

    if is_webview2_process(app_name):
        return WebView2Profile(config)

    return GenericAppProfile(config)


__all__ = [
    "BaseAppProfile",
    "FileExplorerProfile",
    "GenericAppProfile",
    "NotepadProfile",
    "OutlookProfile",
    "WebView2Profile",
    "get_profile",
]
