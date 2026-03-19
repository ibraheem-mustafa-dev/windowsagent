"""Tests for the voice activation and pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestVoicePipeline:
    def test_pipeline_creates_with_config(self) -> None:
        from windowsagent.voice.pipeline import VoicePipeline

        mock_stt = MagicMock()
        pipeline = VoicePipeline(stt_backend=mock_stt)
        assert pipeline.stt_backend is mock_stt

    def test_pipeline_transcribe_calls_stt(self) -> None:
        from windowsagent.voice.pipeline import VoicePipeline

        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "open notepad"
        pipeline = VoicePipeline(stt_backend=mock_stt)
        result = pipeline.transcribe_file("test.wav")
        assert result == "open notepad"
        mock_stt.transcribe.assert_called_once_with("test.wav")

    def test_pipeline_returns_empty_on_stt_error(self) -> None:
        from windowsagent.voice.pipeline import VoicePipeline

        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = RuntimeError("API error")
        pipeline = VoicePipeline(stt_backend=mock_stt)
        result = pipeline.transcribe_file("test.wav")
        assert result == ""

    def test_pipeline_sample_rate(self) -> None:
        from windowsagent.voice.pipeline import SAMPLE_RATE

        assert SAMPLE_RATE == 16000

    def test_pipeline_channels(self) -> None:
        from windowsagent.voice.pipeline import CHANNELS

        assert CHANNELS == 1
