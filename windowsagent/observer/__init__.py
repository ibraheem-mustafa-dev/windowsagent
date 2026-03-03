"""
Observer module — captures the current state of a Windows application.

Components:
- screenshot.py: Fast screen/window capture via mss
- uia.py: Windows UI Automation tree inspection via pywinauto
- ocr.py: Text extraction via Windows OCR API or Tesseract
- state.py: Combined AppState snapshot
"""

from windowsagent.observer.screenshot import Screenshot, capture_full, capture_window, list_monitors
from windowsagent.observer.state import AppState, StateDiff, capture, diff
from windowsagent.observer.uia import (
    UIAElement,
    UIATree,
    WindowInfo,
    find_element,
    get_tree,
    get_windows,
    is_webview2,
)

__all__ = [
    "AppState",
    "Screenshot",
    "StateDiff",
    "UIAElement",
    "UIATree",
    "WindowInfo",
    "capture",
    "capture_full",
    "capture_window",
    "diff",
    "find_element",
    "get_tree",
    "get_windows",
    "is_webview2",
    "list_monitors",
]
