"""
Configuration system for WindowsAgent.

Loads settings from (in ascending priority):
1. Dataclass defaults
2. ~/.windowsagent/config.json
3. pyproject.toml [tool.windowsagent] section in the current working directory
4. Environment variables prefixed with WINDOWSAGENT_

Example environment variable overrides:
    WINDOWSAGENT_VISION_MODEL=claude-haiku
    WINDOWSAGENT_UIA_TIMEOUT=10.0
    WINDOWSAGENT_LOG_LEVEL=DEBUG
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Sensitive action keywords — require confirmation when confirm_sensitive=True
SENSITIVE_ACTION_KEYWORDS: tuple[str, ...] = (
    "delete",
    "remove",
    "send",
    "submit",
    "purchase",
    "buy",
    "pay",
    "confirm",
    "overwrite",
    "format",
)


@dataclass
class Config:
    """Full configuration for WindowsAgent.

    All settings can be overridden via environment variables using the
    WINDOWSAGENT_ prefix followed by the field name in uppercase.
    For example: WINDOWSAGENT_UIA_TIMEOUT=10.0
    """

    # ── Vision model ────────────────────────────────────────────────
    # Supported: "gemini-flash", "claude-haiku", "claude-sonnet", "none"
    vision_model: str = "gemini-flash"

    # Auto-loaded from GEMINI_API_KEY or ANTHROPIC_API_KEY env vars if empty.
    # When vision_model="none", this is ignored.
    vision_api_key: str = ""

    # ── Screenshot backend ──────────────────────────────────────────
    # Supported: "mss" (fast, recommended), "pyautogui" (fallback)
    screenshot_backend: str = "mss"

    # ── OCR backend ─────────────────────────────────────────────────
    # Supported: "windows" (built-in WinRT), "tesseract" (requires pytesseract),
    # "none" (disable OCR entirely)
    ocr_backend: str = "windows"

    # ── Timeouts (seconds) ──────────────────────────────────────────
    # How long to wait for a UIA element to appear
    uia_timeout: float = 5.0
    # How long to wait for a vision model API response
    vision_timeout: float = 15.0
    # How long to wait for a state change after an action
    verify_timeout: float = 3.0
    # Maximum duration for a full task (Phase 2+)
    task_timeout: float = 300.0

    # ── Retry behaviour ─────────────────────────────────────────────
    max_retries: int = 3
    retry_delay: float = 0.5

    # ── Safety ──────────────────────────────────────────────────────
    # When True, actions matching SENSITIVE_ACTION_KEYWORDS prompt for confirmation
    confirm_sensitive: bool = True
    # Hard limit on actions per task to prevent infinite loops
    max_actions_per_task: int = 200

    # ── Record/Replay (Phase 2 — not implemented in Phase 1) ────────
    record_replays: bool = False
    replay_dir: str = "./replays"

    # ── HTTP Server ─────────────────────────────────────────────────
    # IMPORTANT: Always keep this as 127.0.0.1 unless you understand the
    # security implications of exposing the agent API on a network interface.
    server_host: str = "127.0.0.1"
    server_port: int = 7862

    # ── Logging ─────────────────────────────────────────────────────
    # Supported: "DEBUG", "INFO", "WARNING", "ERROR"
    log_level: str = "INFO"

    # ── UIA tree caching ────────────────────────────────────────────
    # Seconds to cache UIA tree results before re-inspecting
    uia_cache_ttl: float = 0.5

    def __post_init__(self) -> None:
        """Resolve api_key from environment if not explicitly set."""
        if not self.vision_api_key:
            if self.vision_model.startswith("gemini"):
                self.vision_api_key = os.environ.get("GEMINI_API_KEY", "")
            elif self.vision_model.startswith("claude"):
                self.vision_api_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if self.server_host != "127.0.0.1":
            logger.warning(
                "Server is configured to bind on %s — this exposes the agent API "
                "beyond localhost. Ensure this is intentional.",
                self.server_host,
            )


def _load_json_config(path: Path) -> dict[str, Any]:
    """Load a JSON config file, returning empty dict on any error."""
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("Config file %s is not a JSON object, ignoring.", path)
            return {}
        return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning("Config file %s is invalid JSON: %s", path, exc)
        return {}
    except OSError as exc:
        logger.warning("Could not read config file %s: %s", path, exc)
        return {}


def _load_pyproject_config(cwd: Path) -> dict[str, Any]:
    """Load [tool.windowsagent] section from pyproject.toml if present."""
    pyproject = cwd / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        # Use tomllib (Python 3.11+) or tomli as fallback
        try:
            import tomllib  # type: ignore[import]
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[import,no-redef]
            except ImportError:
                logger.debug("tomllib/tomli not available; skipping pyproject.toml config.")
                return {}

        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        return data.get("tool", {}).get("windowsagent", {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not parse pyproject.toml: %s", exc)
        return {}


def _apply_dict_to_config(config_dict: dict[str, Any], target: Config) -> None:
    """Apply a flat key→value dict to a Config instance, ignoring unknown keys."""
    valid_fields = {f.name for f in fields(Config)}
    for key, value in config_dict.items():
        if key in valid_fields:
            try:
                # Cast to the field's type if needed
                field_type = type(getattr(target, key))
                setattr(target, key, field_type(value))
            except (TypeError, ValueError) as exc:
                logger.warning("Invalid config value for %s=%r: %s", key, value, exc)
        else:
            logger.debug("Unknown config key %r ignored.", key)


def _apply_env_vars(target: Config) -> None:
    """Override config fields from WINDOWSAGENT_* environment variables."""
    prefix = "WINDOWSAGENT_"
    valid_fields = {f.name: f for f in fields(Config)}
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        field_name = env_key[len(prefix):].lower()
        if field_name not in valid_fields:
            continue
        field_type = type(getattr(target, field_name))
        try:
            if field_type is bool:
                setattr(target, field_name, env_value.lower() in ("1", "true", "yes"))
            else:
                setattr(target, field_name, field_type(env_value))
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Invalid env var %s=%r: %s", env_key, env_value, exc
            )


def load_config(cwd: Path | None = None) -> Config:
    """Load Config from all sources in priority order.

    Priority (highest wins):
    1. Environment variables (WINDOWSAGENT_*)
    2. pyproject.toml [tool.windowsagent]
    3. ~/.windowsagent/config.json
    4. Dataclass defaults

    Args:
        cwd: Directory to search for pyproject.toml. Defaults to current directory.

    Returns:
        Fully resolved Config instance.
    """
    if cwd is None:
        cwd = Path.cwd()

    config = Config()

    # Layer 1: User config file
    user_config_path = Path.home() / ".windowsagent" / "config.json"
    user_data = _load_json_config(user_config_path)
    if user_data:
        logger.debug("Loaded user config from %s", user_config_path)
        _apply_dict_to_config(user_data, config)

    # Layer 2: pyproject.toml
    pyproject_data = _load_pyproject_config(cwd)
    if pyproject_data:
        logger.debug("Loaded pyproject.toml [tool.windowsagent] config")
        _apply_dict_to_config(pyproject_data, config)

    # Layer 3: Environment variables
    _apply_env_vars(config)

    # Re-run post_init to resolve api_key after all sources are applied
    config.__post_init__()

    return config
