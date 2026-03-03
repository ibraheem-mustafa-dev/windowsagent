"""
Exception hierarchy for WindowsAgent.

All exceptions inherit from WindowsAgentError. The retryable flag guides
the agent loop's retry logic — True means the operation is worth retrying,
False means it's a hard failure.
"""

from __future__ import annotations

from typing import Any


class WindowsAgentError(Exception):
    """Base exception for all WindowsAgent errors."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.context: dict[str, Any] = context or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, retryable={self.retryable})"


# ── Observer exceptions ─────────────────────────────────────────────────────


class ObserverError(WindowsAgentError):
    """Base class for observer module errors."""


class ScreenshotError(ObserverError):
    """Failed to capture a screenshot."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message, retryable=retryable)


class UIAError(ObserverError):
    """Base class for UI Automation errors."""


class WindowNotFoundError(UIAError):
    """Target window could not be found."""

    def __init__(self, title: str, retryable: bool = True) -> None:
        super().__init__(
            f"Window not found: {title!r}",
            retryable=retryable,
            context={"title": title},
        )
        self.title = title


class ElementNotFoundError(UIAError):
    """Target element could not be found in the UIA tree."""

    def __init__(self, criteria: dict[str, Any], retryable: bool = True) -> None:
        criteria_str = ", ".join(f"{k}={v!r}" for k, v in criteria.items() if v is not None)
        super().__init__(
            f"Element not found: {criteria_str}",
            retryable=retryable,
            context={"criteria": criteria},
        )
        self.criteria = criteria


class OCRError(ObserverError):
    """OCR backend failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


# ── Grounder exceptions ─────────────────────────────────────────────────────


class GrounderError(WindowsAgentError):
    """Base class for grounder module errors."""


class GroundingFailedError(GrounderError):
    """Could not ground the target description to any UI element."""

    def __init__(self, description: str, methods_tried: list[str]) -> None:
        methods_str = ", ".join(methods_tried)
        super().__init__(
            f"Could not ground {description!r} using methods: {methods_str}",
            retryable=False,
            context={"description": description, "methods_tried": methods_tried},
        )
        self.description = description
        self.methods_tried = methods_tried


class VisionGrounderError(GrounderError):
    """Vision model API call failed."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message, retryable=retryable)


# ── Actor exceptions ────────────────────────────────────────────────────────


class ActorError(WindowsAgentError):
    """Base class for actor module errors."""


class ActionFailedError(ActorError):
    """An action failed after all retries."""

    def __init__(
        self,
        action: str,
        reason: str,
        retryable: bool = True,
        element_name: str | None = None,
    ) -> None:
        element_info = f" on {element_name!r}" if element_name else ""
        super().__init__(
            f"Action {action!r}{element_info} failed: {reason}",
            retryable=retryable,
            context={"action": action, "reason": reason, "element_name": element_name},
        )
        self.action = action
        self.reason = reason


class ElementDisabledError(ActorError):
    """Cannot act on a disabled element."""

    def __init__(self, element_name: str) -> None:
        super().__init__(
            f"Element {element_name!r} is disabled",
            retryable=True,
            context={"element_name": element_name},
        )
        self.element_name = element_name


class ElementNotVisibleError(ActorError):
    """Cannot act on an element that is off-screen or hidden."""

    def __init__(self, element_name: str) -> None:
        super().__init__(
            f"Element {element_name!r} is not visible",
            retryable=True,
            context={"element_name": element_name},
        )
        self.element_name = element_name


# ── Verifier exceptions ─────────────────────────────────────────────────────


class VerifierError(WindowsAgentError):
    """Base class for verifier module errors."""


class VerificationTimeoutError(VerifierError):
    """State did not change within the allowed timeout."""

    def __init__(self, timeout: float) -> None:
        super().__init__(
            f"No state change detected within {timeout:.1f}s",
            retryable=True,
            context={"timeout": timeout},
        )
        self.timeout = timeout
