"""Tests for STT backend abstraction."""
from __future__ import annotations

import pytest


class TestSTTBackendFactory:
    def test_creates_groq_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("groq", api_key="test-key")
        assert backend is not None
        assert backend.name == "groq"

    def test_creates_openai_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("openai", api_key="test-key")
        assert backend is not None
        assert backend.name == "openai"

    def test_creates_local_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("local", model_size="base")
        assert backend is not None
        assert backend.name == "local"

    def test_creates_self_hosted_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("self-hosted", base_url="http://localhost:8000")
        assert backend is not None
        assert backend.name == "self-hosted"

    def test_off_returns_none(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("off")
        assert backend is None

    def test_unknown_backend_raises(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        with pytest.raises(ValueError, match="Unknown STT backend"):
            create_stt_backend("nonexistent")

    def test_self_hosted_without_url_raises(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        with pytest.raises(ValueError, match="base_url"):
            create_stt_backend("self-hosted")


class TestOpenAICompatibleSTT:
    def test_groq_base_url(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("groq", api_key="k")
        assert backend is not None
        assert "groq.com" in backend.base_url  # type: ignore[attr-defined]

    def test_openai_model(self) -> None:
        from windowsagent.voice.stt import create_stt_backend

        backend = create_stt_backend("openai", api_key="k")
        assert backend is not None
        assert backend.model == "whisper-1"  # type: ignore[attr-defined]


class TestLocalWhisperSTT:
    def test_lazy_model_loading(self) -> None:
        from windowsagent.voice.stt import LocalWhisperSTT

        stt = LocalWhisperSTT(model_size="tiny")
        # Model should not be loaded until transcribe() is called
        assert stt._model is None


class TestConfigVoiceFields:
    def test_default_stt_backend_is_off(self) -> None:
        from windowsagent.config import Config

        config = Config()
        assert config.stt_backend == "off"

    def test_voice_hotkey_default(self) -> None:
        from windowsagent.config import Config

        config = Config()
        assert config.voice_hotkey == "ctrl+shift+space"

    def test_stt_fields_exist(self) -> None:
        from windowsagent.config import Config

        config = Config()
        assert hasattr(config, "stt_api_key")
        assert hasattr(config, "stt_base_url")
        assert hasattr(config, "stt_local_model")
