"""
Vision Grounder — match a UI element description to screen coordinates
using a vision language model.

This is the fallback when UIA grounding fails. The vision model receives
a screenshot and a natural language description, then returns the centre
coordinates of the matching element.

Supported models:
- gemini-flash (default): Gemini 2.5 Flash via google-generativeai
- claude-haiku: Claude Haiku via anthropic
- claude-sonnet: Claude Sonnet via anthropic

The response is always parsed as JSON: {"x": int, "y": int} or {"found": false}.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import TYPE_CHECKING

from windowsagent.exceptions import VisionGrounderError
from windowsagent.grounder.uia_grounder import GroundedElement

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.screenshot import Screenshot

logger = logging.getLogger(__name__)

# System prompt for vision grounding
VISION_SYSTEM_PROMPT = """You are a UI element locator. Given a screenshot and a description of a UI element,
return the centre coordinates of that element.

RESPOND ONLY WITH JSON. No explanation. No markdown.

If the element is visible: {"x": <integer>, "y": <integer>}
If the element is not visible: {"found": false}

The coordinates must be within the screenshot dimensions."""

VISION_USER_PROMPT = """Find the UI element described as: "{description}"

Return ONLY JSON with the centre (x, y) coordinates in pixels, or {{"found": false}} if not visible."""


def ground(
    description: str,
    screenshot: "Screenshot",
    config: "Config",
) -> GroundedElement | None:
    """Locate a UI element using a vision language model.

    Args:
        description: Natural language description of the target element.
        screenshot: Current screenshot to analyse.
        config: WindowsAgent configuration (determines model and API key).

    Returns:
        GroundedElement with method="vision", or None if element not found.

    Raises:
        VisionGrounderError: If the API call fails or returns invalid data.
    """
    if config.vision_model == "none":
        logger.debug("Vision grounding disabled (vision_model='none')")
        return None

    if not config.vision_api_key:
        logger.warning(
            "Vision grounding requested but no API key configured. "
            "Set GEMINI_API_KEY or ANTHROPIC_API_KEY."
        )
        return None

    screenshot_b64 = _encode_screenshot(screenshot)

    try:
        if config.vision_model.startswith("gemini"):
            coords = _call_gemini(description, screenshot_b64, config)
        elif config.vision_model.startswith("claude"):
            coords = _call_claude(description, screenshot_b64, config)
        else:
            raise VisionGrounderError(
                f"Unknown vision model: {config.vision_model!r}. "
                "Supported: gemini-flash, claude-haiku, claude-sonnet"
            )
    except VisionGrounderError:
        raise

    if coords is None:
        logger.debug("Vision grounding: element %r not found in screenshot", description)
        return None

    x, y = coords

    # Validate coordinates are within the screenshot
    if not (0 <= x <= screenshot.logical_width and 0 <= y <= screenshot.logical_height):
        logger.warning(
            "Vision model returned out-of-bounds coordinates (%d, %d) for image %dx%d",
            x, y, screenshot.logical_width, screenshot.logical_height,
        )
        return None

    logger.debug("Vision grounding: %r -> (%d, %d)", description, x, y)
    return GroundedElement(
        method="vision",
        uia_element=None,
        coordinates=(x, y),
        confidence=0.75,  # Vision grounding is less precise than UIA
        bounding_rect=(max(0, x - 20), max(0, y - 10), x + 20, y + 10),
        description_matched=description,
    )


# ── Private helpers ──────────────────────────────────────────────────────────


def _encode_screenshot(screenshot: "Screenshot") -> str:
    """Encode a screenshot as base64 PNG for API submission."""
    try:
        buf = io.BytesIO()
        screenshot.image.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as exc:
        raise VisionGrounderError(f"Failed to encode screenshot: {exc}") from exc


def _parse_coordinates_response(response_text: str) -> tuple[int, int] | None:
    """Parse JSON response from vision model into (x, y) or None."""
    # Strip any markdown fences
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VisionGrounderError(f"Vision model returned invalid JSON: {exc}\nResponse: {text!r}") from exc

    if data.get("found") is False:
        return None

    if "x" not in data or "y" not in data:
        raise VisionGrounderError(f"Vision model response missing x/y keys: {data}")

    try:
        return (int(data["x"]), int(data["y"]))
    except (TypeError, ValueError) as exc:
        raise VisionGrounderError(f"Vision model returned non-integer coordinates: {data}") from exc


def _call_gemini(
    description: str,
    screenshot_b64: str,
    config: "Config",
) -> tuple[int, int] | None:
    """Call Gemini Flash API for vision grounding."""
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise VisionGrounderError(
            "google-generativeai not installed. Install with: pip install windowsagent[vision]"
        ) from exc

    try:
        genai.configure(api_key=config.vision_api_key)

        model_name = config.vision_model if config.vision_model.startswith("gemini") else "gemini-2.5-flash"
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=VISION_SYSTEM_PROMPT,
        )

        # Convert base64 back to bytes for the API
        image_bytes = base64.b64decode(screenshot_b64)
        image_part = {"mime_type": "image/png", "data": image_bytes}

        prompt = VISION_USER_PROMPT.format(description=description)
        response = model.generate_content(
            [image_part, prompt],
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                max_output_tokens=64,
            ),
        )

        response_text = response.text.strip()
        return _parse_coordinates_response(response_text)

    except VisionGrounderError:
        raise
    except Exception as exc:
        raise VisionGrounderError(
            f"Gemini API call failed: {exc}", retryable=True
        ) from exc


def _call_claude(
    description: str,
    screenshot_b64: str,
    config: "Config",
) -> tuple[int, int] | None:
    """Call Claude Haiku/Sonnet API for vision grounding."""
    try:
        import anthropic
    except ImportError as exc:
        raise VisionGrounderError(
            "anthropic not installed. Install with: pip install windowsagent[vision]"
        ) from exc

    try:
        model_map = {
            "claude-haiku": "claude-haiku-4-5-20251001",
            "claude-sonnet": "claude-sonnet-4-6",
        }
        model_id = model_map.get(config.vision_model, "claude-haiku-4-5-20251001")

        client = anthropic.Anthropic(api_key=config.vision_api_key)
        message = client.messages.create(
            model=model_id,
            max_tokens=64,
            system=VISION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": VISION_USER_PROMPT.format(description=description),
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text.strip()
        return _parse_coordinates_response(response_text)

    except VisionGrounderError:
        raise
    except Exception as exc:
        raise VisionGrounderError(
            f"Claude API call failed: {exc}", retryable=True
        ) from exc
