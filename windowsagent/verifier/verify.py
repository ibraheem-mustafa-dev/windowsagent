"""
Verifier module — confirms that actions produced the expected change.

The verifier is called after every action in the agent loop. If verification
fails (no change detected), the agent retries or reports failure.

Verification strategies:
1. Screenshot diff: Compare pixel-level change (fast, always applicable)
2. UIA element comparison: Check if a specific element's value changed
3. wait_for_change: Poll until any change is detected (for async operations)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.screenshot import Screenshot
    from windowsagent.observer.state import AppState
    from windowsagent.observer.uia import UIAElement

logger = logging.getLogger(__name__)

# Minimum pixel change fraction to consider a screenshot "changed"
CHANGE_THRESHOLD = 0.02  # 2%

# Poll interval for wait_for_change
POLL_INTERVAL = 0.1  # seconds


def screenshot_diff(before: Screenshot, after: Screenshot) -> float:
    """Compute the fraction of pixels that changed between two screenshots.

    Args:
        before: Screenshot captured before an action.
        after: Screenshot captured after an action.

    Returns:
        Float from 0.0 (identical) to 1.0 (completely different).
    """
    try:

        from PIL import Image, ImageChops

        img_before = before.image
        img_after = after.image

        # Resize to match if dimensions differ (DPI changes, window resize)
        if img_before.size != img_after.size:
            # Resize the smaller to match the larger
            target_size = (
                max(img_before.width, img_after.width),
                max(img_before.height, img_after.height),
            )
            if img_before.size != target_size:
                img_before = img_before.resize(target_size, Image.Resampling.LANCZOS)
            if img_after.size != target_size:
                img_after = img_after.resize(target_size, Image.Resampling.LANCZOS)

        # Ensure both are RGB
        if img_before.mode != "RGB":
            img_before = img_before.convert("RGB")
        if img_after.mode != "RGB":
            img_after = img_after.convert("RGB")

        # Try numpy path (faster)
        try:
            import numpy as np
            arr_before = np.array(img_before, dtype=np.float32)
            arr_after = np.array(img_after, dtype=np.float32)
            diff = np.abs(arr_before - arr_after)
            # Sum of all channel diffs, normalised to [0, 1]
            total_possible = arr_before.shape[0] * arr_before.shape[1] * 255.0 * 3
            diff_fraction = float(np.sum(diff) / total_possible)
            return min(1.0, diff_fraction)
        except ImportError:
            pass

        # PIL fallback (slower)
        diff_img = ImageChops.difference(img_before, img_after)
        pixel_data = list(diff_img.getdata())
        channel_sum = sum(sum(pixel) for pixel in pixel_data)
        total_possible = img_before.width * img_before.height * 255.0 * 3
        return float(min(1.0, channel_sum / total_possible))

    except Exception as exc:
        logger.warning("Screenshot diff failed: %s", exc)
        return 0.0


def uia_element_changed(
    before: UIAElement,
    after: UIAElement,
) -> bool:
    """Return True if an element's visible state changed between two captures.

    Compares name, value, is_enabled, and is_visible.

    Args:
        before: Element state before the action.
        after: Element state after the action.

    Returns:
        True if any meaningful property changed.
    """
    return (
        before.name != after.name
        or before.value != after.value
        or before.is_enabled != after.is_enabled
        or before.is_visible != after.is_visible
    )


def action_succeeded(
    before: AppState,
    after: AppState,
    action: str,
    target: str,
) -> bool:
    """Heuristic check whether an action produced the expected change.

    This is a best-effort check. It combines screenshot diff with UIA
    state comparison to give a confidence verdict.

    Args:
        before: AppState captured before the action.
        after: AppState captured after the action.
        action: Action type string (e.g. "click", "type", "scroll").
        target: Target element description.

    Returns:
        True if evidence suggests the action succeeded.
    """
    # Screenshot diff check (works for all actions)
    diff = screenshot_diff(before.screenshot, after.screenshot)

    if diff > CHANGE_THRESHOLD:
        logger.debug(
            "action_succeeded: screenshot diff %.1f%% > threshold %.1f%%",
            diff * 100,
            CHANGE_THRESHOLD * 100,
        )
        return True

    # UIA tree check — look for any changed element
    try:
        from windowsagent.observer.state import diff as state_diff
        s_diff = state_diff(before, after)
        if s_diff.changed_elements or s_diff.new_elements or s_diff.removed_elements:
            logger.debug(
                "action_succeeded: UIA tree changed (%d new, %d removed, %d changed elements)",
                len(s_diff.new_elements),
                len(s_diff.removed_elements),
                len(s_diff.changed_elements),
            )
            return True
    except Exception as exc:
        logger.debug("UIA state diff failed: %s", exc)

    # No change detected
    logger.debug(
        "action_succeeded: no change detected (screenshot diff=%.2f%%, action=%r, target=%r)",
        diff * 100,
        action,
        target,
    )
    return False


def wait_for_change(
    hwnd: int,
    config: Config,
    timeout: float | None = None,
) -> bool:
    """Poll until a change is detected in the window's screenshot.

    Used after actions that trigger asynchronous UI updates (e.g. loading a
    page, sending an email, opening a dialog).

    Args:
        hwnd: Window handle to monitor.
        config: WindowsAgent configuration.
        timeout: Override timeout in seconds. Defaults to config.verify_timeout.

    Returns:
        True if a change was detected within the timeout.
        False if timeout elapsed without any change.
    """
    from windowsagent.observer.screenshot import capture_window

    actual_timeout = timeout if timeout is not None else config.verify_timeout
    deadline = time.monotonic() + actual_timeout

    try:
        baseline = capture_window(hwnd, config)
    except Exception as exc:
        logger.warning("Could not capture baseline for wait_for_change: %s", exc)
        return False

    poll_count = 0
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        poll_count += 1

        try:
            current = capture_window(hwnd, config)
            diff = screenshot_diff(baseline, current)
            if diff > CHANGE_THRESHOLD:
                logger.debug(
                    "wait_for_change: change detected after %d polls (diff=%.1f%%)",
                    poll_count,
                    diff * 100,
                )
                return True
        except Exception as exc:
            logger.debug("wait_for_change poll failed: %s", exc)

    logger.debug(
        "wait_for_change: no change after %.1fs (%d polls)", actual_timeout, poll_count
    )
    return False
