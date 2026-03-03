"""
Verifier module — confirms that an action produced the expected change.

Components:
- verify.py: Screenshot diff, UIA state comparison, wait-for-change polling
"""

from windowsagent.verifier.verify import (
    action_succeeded,
    screenshot_diff,
    uia_element_changed,
    wait_for_change,
)

__all__ = [
    "action_succeeded",
    "screenshot_diff",
    "uia_element_changed",
    "wait_for_change",
]
