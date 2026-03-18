"""
Hybrid Grounder — try UIA first, fall back to vision automatically.

This is the single entry point the agent loop uses. It never calls
uia_grounder or vision_grounder directly.

Decision logic:
1. Try UIA grounding with the full accessibility tree
2. If confidence >= 0.7, return the UIA result immediately
3. If UIA returns low confidence or None, try vision grounding (if configured)
4. Return the best result, or None if all methods fail

Logging records which method succeeded and the confidence, so users can
diagnose why a particular action used the slower vision path.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from windowsagent.grounder.uia_grounder import GroundedElement
from windowsagent.grounder.uia_grounder import ground as uia_ground

if TYPE_CHECKING:
    from windowsagent.apps.base import BaseAppProfile
    from windowsagent.config import Config
    from windowsagent.observer.state import AppState

logger = logging.getLogger(__name__)

# Confidence threshold below which we try the vision fallback
UIA_CONFIDENCE_THRESHOLD = 0.7


def ground(
    description: str,
    state: AppState,
    config: Config,
    profile: BaseAppProfile | None = None,
) -> GroundedElement | None:
    """Ground a natural language description to a UI element.

    Resolution order:
    1. Profile-hint exact match — if the app profile knows the exact UIA name,
       use it directly (confidence 0.95). Skips fuzzy tree scan.
    2. UIA tree scan — fuzzy keyword + type matching.
    3. Vision fallback — Gemini/Claude screenshot analysis if UIA fails.

    Args:
        description: Natural language description (e.g. "the Send button").
        state: Current AppState (contains UIA tree and screenshot).
        config: WindowsAgent configuration.
        profile: App-specific profile. If provided, its known_elements map is
            checked before the fuzzy UIA scan for faster, more reliable grounding.

    Returns:
        GroundedElement (from profile hint, UIA, or vision), or None if all fail.
    """
    methods_tried: list[str] = []

    # ── Profile-hint fast path ─────────────────────────────────────────────
    if profile is not None:
        hint = profile.get_element_hint(description)
        if hint:
            from windowsagent.observer.uia import find_element
            element = find_element(state.uia_tree, name=hint)
            if element:
                logger.debug(
                    "Grounded %r via profile hint %r (confidence=0.95, profile=%r)",
                    description, hint, type(profile).__name__,
                )
                return GroundedElement(
                    method="uia",
                    uia_element=element,
                    coordinates=element.centre,
                    confidence=0.95,
                    bounding_rect=element.rect,
                    description_matched=description,
                )
            else:
                logger.debug(
                    "Profile hint %r for %r not found in tree — falling back to scan",
                    hint, description,
                )

    # ── UIA grounding ──────────────────────────────────────────────────────
    methods_tried.append("uia")
    uia_result: GroundedElement | None = None

    try:
        uia_result = uia_ground(description, state.uia_tree)
        if uia_result and uia_result.confidence >= UIA_CONFIDENCE_THRESHOLD:
            logger.debug(
                "Grounded %r via UIA (confidence=%.2f, element=%r)",
                description,
                uia_result.confidence,
                uia_result.uia_element.name if uia_result.uia_element else "?",
            )
            return uia_result
        elif uia_result:
            logger.debug(
                "UIA grounding returned low confidence %.2f for %r — trying vision",
                uia_result.confidence,
                description,
            )
    except Exception as exc:
        logger.warning("UIA grounding raised an exception: %s", exc)

    # ── Vision grounding fallback ──────────────────────────────────────────
    if config.vision_model != "none" and config.vision_api_key:
        methods_tried.append("vision")
        try:
            from windowsagent.grounder.vision_grounder import ground as vision_ground

            vision_result = vision_ground(description, state.screenshot, config)
            if vision_result:
                logger.info(
                    "Grounded %r via vision fallback (confidence=%.2f, coords=%s). "
                    "UIA confidence was %.2f.",
                    description,
                    vision_result.confidence,
                    vision_result.coordinates,
                    uia_result.confidence if uia_result else 0.0,
                )
                return vision_result
        except Exception as exc:
            logger.warning("Vision grounding failed: %s", exc)
    else:
        logger.debug(
            "Vision grounding not attempted (vision_model=%r, api_key_set=%s)",
            config.vision_model,
            bool(config.vision_api_key),
        )

    # ── Return best available (even if low confidence) ─────────────────────
    if uia_result:
        logger.warning(
            "Returning low-confidence UIA result (%.2f) for %r — "
            "vision grounding was not available or also failed",
            uia_result.confidence,
            description,
        )
        return uia_result

    logger.debug("All grounding methods failed for %r (tried: %s)", description, ", ".join(methods_tried))
    return None
