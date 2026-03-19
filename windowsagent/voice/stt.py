"""
Speech-to-text backend abstraction.

All backends implement the same interface: transcribe(audio_path) -> str.
The OpenAI-compatible API format (POST /v1/audio/transcriptions) is the
standard — Groq, OpenAI, and self-hosted Speaches all use it.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class STTBackend(ABC):
    """Abstract speech-to-text backend."""

    name: str

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file to text.

        Args:
            audio_path: Path to WAV/MP3 audio file.

        Returns:
            Transcribed text string.
        """
        ...


class OpenAICompatibleSTT(STTBackend):
    """STT backend using the OpenAI-compatible /v1/audio/transcriptions API.

    Works with Groq, OpenAI, and self-hosted servers (Speaches, whisper-asr-webservice).
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_path: str) -> str:
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                f"{self.base_url}/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": self.model, "language": "en"},
                timeout=30.0,
            )
            resp.raise_for_status()
            result: str = resp.json().get("text", "").strip()
            return result


class LocalWhisperSTT(STTBackend):
    """STT backend using faster-whisper running locally on the CPU."""

    name = "local"

    def __init__(self, model_size: str = "base") -> None:
        self._model_size = model_size
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Loaded faster-whisper model: %s", self._model_size)
        return self._model

    def transcribe(self, audio_path: str) -> str:
        model = self._load_model()
        segments, _info = model.transcribe(audio_path, language="en")
        return " ".join(s.text.strip() for s in segments).strip()


def create_stt_backend(
    backend: str,
    api_key: str = "",
    base_url: str = "",
    model_size: str = "base",
) -> STTBackend | None:
    """Create an STT backend by name.

    Args:
        backend: "groq", "openai", "self-hosted", "local", or "off"
        api_key: API key for cloud backends.
        base_url: Base URL for self-hosted backend.
        model_size: Whisper model size for local backend.

    Returns:
        STTBackend instance, or None if "off".
    """
    if backend == "off":
        return None

    if backend == "groq":
        return OpenAICompatibleSTT(
            name="groq",
            base_url="https://api.groq.com/openai",
            api_key=api_key,
            model="whisper-large-v3-turbo",
        )

    if backend == "openai":
        return OpenAICompatibleSTT(
            name="openai",
            base_url="https://api.openai.com",
            api_key=api_key,
            model="whisper-1",
        )

    if backend == "self-hosted":
        if not base_url:
            raise ValueError("Self-hosted STT requires a base_url")
        return OpenAICompatibleSTT(
            name="self-hosted",
            base_url=base_url,
            api_key=api_key,
            model="whisper-large-v3-turbo",
        )

    if backend == "local":
        return LocalWhisperSTT(model_size=model_size)

    raise ValueError(f"Unknown STT backend: {backend!r}")
