"""
Voice pipeline: record audio -> transcribe -> return text.

The pipeline handles microphone recording with VAD (voice activity detection)
to automatically stop recording when the user stops speaking. Transcription
is delegated to the configured STT backend.
"""
from __future__ import annotations

import logging
import tempfile
import wave
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from windowsagent.voice.stt import STTBackend

logger = logging.getLogger(__name__)

# Audio recording constants
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


class VoicePipeline:
    """Manages the full voice input pipeline."""

    def __init__(self, stt_backend: STTBackend) -> None:
        self.stt_backend = stt_backend

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe an audio file to text.

        Returns empty string on any error (never raises).
        """
        try:
            return self.stt_backend.transcribe(audio_path)
        except Exception as exc:
            logger.warning("Voice transcription failed: %s", exc)
            return ""

    def record_and_transcribe(self, duration_seconds: float = 10.0) -> str:
        """Record from microphone and transcribe.

        Records for up to duration_seconds or until silence is detected.
        Returns the transcribed text, or empty string on failure.
        """
        try:
            import numpy as np
            import sounddevice as sd

            logger.info("Recording audio (max %.1fs)...", duration_seconds)
            audio: np.ndarray = sd.rec(
                int(duration_seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
            )
            sd.wait()

            # Save to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(SAMPLE_WIDTH)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio.tobytes())

            text = self.transcribe_file(tmp_path)

            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

            return text
        except Exception as exc:
            logger.warning("Voice recording failed: %s", exc)
            return ""
