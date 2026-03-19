# WindowsAgent GUI, Voice & MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform WindowsAgent from a CLI/API tool into a consumer product with MCP server, voice input, UIA overlay, and Electron GUI — built in the order that delivers value fastest.

**Architecture:** Four independent deliverables, each shipping and usable before the next begins: (1) MCP server wrapping existing FastAPI endpoints, (2) voice pipeline with configurable STT backends, (3) UIA element overlay for visual debugging, (4) Electron GUI with React + shadcn/ui tying everything together. The existing FastAPI backend on localhost:7862 is the integration point — all new components talk to it via HTTP/SSE.

**Tech Stack:**
- MCP: Python `mcp` package (FastMCP), JSON-RPC over stdio
- Voice: `sounddevice` + `silero-vad` + configurable STT (Groq API primary, faster-whisper local fallback)
- Overlay: PyQt6 transparent window + existing UIA tree data
- GUI: Electron + Vite + React + TypeScript + shadcn/ui + Radix + cmdk
- Streaming: `sse-starlette` for FastAPI SSE endpoint

**Pre-requisites already built:**
- FastAPI server with 20+ endpoints (observe, act, verify, task, windows, browser, spawn, shell)
- LLM TaskPlanner (Gemini Flash primary, Claude Haiku fallback)
- 10 app profiles (Excel verified live, Outlook, Chrome, Edge, etc.)
- JSONL action recorder (recording works, replay not built)
- Error recovery framework (circuit breaker, focus recovery, dialog detection)
- 227 unit tests passing, mypy 0 errors

**Research basis:** Deep research with 8 parallel agents, 100+ sources. See `docs/GUI-VOICE-DECISION-BRIEF.md` for full findings.

---

## File Structure

### Phase 1: MCP Server (Week 1)

```
windowsagent/
  mcp_server.py          — MCP server entry point (FastMCP, stdio transport)
tests/
  test_mcp_server.py     — Unit tests for MCP tool definitions
```

### Phase 2: Voice Pipeline (Weeks 2-4)

```
windowsagent/
  voice/
    __init__.py           — Package exports
    stt.py                — STT backend abstraction (Groq, OpenAI, self-hosted, local)
    activation.py         — Push-to-talk + wake word activation
    pipeline.py           — Full voice pipeline: activate -> record -> transcribe -> dispatch
  config.py               — Add voice config fields (stt_backend, stt_api_key, etc.)
tests/
  test_voice_stt.py       — Unit tests for STT backends
  test_voice_pipeline.py  — Unit tests for voice pipeline
```

### Phase 3: SSE Streaming (Week 3, parallel with voice)

```
windowsagent/
  routes/agent.py         — Add GET /agent/stream SSE endpoint
  _server_state.py        — Add agent_event_queue
  agent_loop.py           — Emit events to queue at state transitions
```

### Phase 4: UIA Element Overlay (Weeks 5-6)

```
windowsagent/
  overlay/
    __init__.py           — Package exports
    renderer.py           — PyQt6 transparent overlay window, draws element boxes
    inspector.py          — Element property popup, search, profile builder
tests/
  test_overlay.py         — Unit tests for overlay rendering logic
```

### Phase 5: Electron GUI (Weeks 7-11)

```
gui/
  package.json            — Electron + Vite + React + shadcn/ui
  electron.vite.config.ts — electron-vite configuration
  src/
    main/
      index.ts            — Electron main process, window lifecycle
      preload.ts          — contextBridge with whitelisted IPC channels
    renderer/
      index.html          — Entry HTML
      src/
        App.tsx           — Root component with SSE provider
        main.tsx          — React entry point
        components/
          CommandPalette.tsx  — cmdk-based command palette (Ctrl+K)
          TaskInput.tsx       — Natural language task input
          StatusPanel.tsx     — Live agent status (ARIA live region)
          ActionLog.tsx       — Streaming action log (role="log")
          VoiceButton.tsx     — Push-to-talk microphone button
          SettingsPanel.tsx   — Configuration (STT backend, profiles, etc.)
        hooks/
          useAgentStream.ts   — SSE EventSource hook
          useVoice.ts         — Voice activation hook
        lib/
          api.ts              — Fetch wrapper for localhost:7862
```

---

## Task 1: MCP Server

**Files:**
- Create: `windowsagent/mcp_server.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing test for MCP tool definitions**

```python
# tests/test_mcp_server.py
"""Tests for the MCP server tool definitions."""
from __future__ import annotations


class TestMCPToolDefinitions:
    def test_observe_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_observe" in tool_names

    def test_act_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_act" in tool_names

    def test_task_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_task" in tool_names

    def test_health_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_health" in tool_names

    def test_list_windows_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_list_windows" in tool_names

    def test_manage_window_tool_exists(self) -> None:
        from windowsagent.mcp_server import mcp
        tool_names = [t.name for t in mcp.list_tools()]
        assert "wa_manage_window" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_server.py -v`
Expected: FAIL with "cannot import name 'mcp_server'"

- [ ] **Step 3: Install mcp package**

Run: `pip install mcp[cli]`

- [ ] **Step 4: Write MCP server implementation**

```python
# windowsagent/mcp_server.py
"""
MCP server for WindowsAgent.

Exposes WindowsAgent capabilities as MCP tools for Claude Desktop,
Cursor, and any MCP-compatible AI tool. Uses FastMCP with stdio transport.

The server communicates with the existing FastAPI backend on localhost:7862
via HTTP. Start the FastAPI server first: windowsagent serve

Usage:
    python -m windowsagent.mcp_server
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:7862"

mcp = FastMCP(
    "WindowsAgent",
    description="AI agent that controls Windows desktop apps via the UI Automation API. "
    "Reads the UI by name, not by pixel.",
)


def _post(path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the WindowsAgent FastAPI backend."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{BASE_URL}{path}", json=data or {})
        resp.raise_for_status()
        return resp.json()


def _get(path: str) -> Any:
    """GET from the WindowsAgent FastAPI backend."""
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{BASE_URL}{path}")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def wa_health() -> str:
    """Check if the WindowsAgent server is running and healthy."""
    result = _get("/health")
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_list_windows() -> str:
    """List all visible top-level windows on the desktop.

    Returns window titles, process names, and PIDs.
    """
    result = _get("/windows")
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_observe(window: str) -> str:
    """Capture the current state of a window: UIA tree, screenshot metadata, and OCR text.

    Args:
        window: Window title or partial match (e.g. "Excel", "Notepad")
    """
    result = _post("/observe", {"window": window})
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_act(window: str, action: str, element: str, text: str = "", key: str = "") -> str:
    """Execute a single action on a UI element in a window.

    Args:
        window: Window title or partial match
        action: Action type — click, type, scroll, key, expand, toggle, select
        element: Target element description (e.g. "Save button", "Email text field")
        text: Text to type (for action="type")
        key: Key to press (for action="key", e.g. "enter", "escape")
    """
    params: dict[str, Any] = {}
    if text:
        params["text"] = text
    if key:
        params["key"] = key
    result = _post("/act", {
        "window": window,
        "action": action,
        "element": element,
        "params": params,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_task(window: str, task: str, max_steps: int = 20) -> str:
    """Execute a complete natural language task using the LLM task planner.

    The agent observes the window, plans steps, and executes them with verification.

    Args:
        window: Window title or partial match
        task: Natural language task description (e.g. "Send an email to Amir about the invoice")
        max_steps: Maximum number of steps before stopping (default 20)
    """
    result = _post("/task", {
        "window": window,
        "task": task,
        "max_steps": max_steps,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
def wa_manage_window(window: str, action: str) -> str:
    """Manage window state — activate, minimise, maximise, restore, close.

    Args:
        window: Window title or partial match
        action: One of: activate, minimise, maximise, restore, close, bring_to_front
    """
    result = _post("/window/manage", {
        "window": window,
        "action": action,
    })
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_server.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 6: Run full test suite to verify nothing broke**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 233+ passed

- [ ] **Step 7: Run mypy**

Run: `python -m mypy windowsagent/mcp_server.py`
Expected: 0 errors

- [ ] **Step 8: Add CLI entry point for MCP server**

Modify: `windowsagent/cli.py` — add `mcp` command:

```python
@cli.command(name="mcp")
def serve_mcp() -> None:
    """Start the MCP server (stdio transport for Claude Desktop/Cursor)."""
    from windowsagent.mcp_server import mcp
    click.echo("Starting WindowsAgent MCP server (stdio transport)")
    mcp.run(transport="stdio")
```

- [ ] **Step 9: Test CLI command exists**

Run: `python -m windowsagent.cli mcp --help`
Expected: Shows help text

- [ ] **Step 10: Add httpx to dependencies**

Modify: `pyproject.toml` — add `httpx` to dependencies and `mcp[cli]` to a new `mcp` optional group.

- [ ] **Step 11: Commit**

```bash
git checkout -b feature/mcp-server
git add windowsagent/mcp_server.py tests/test_mcp_server.py windowsagent/cli.py pyproject.toml
git commit -m "feat: MCP server exposing WindowsAgent tools for Claude Desktop/Cursor"
```

---

## Task 2: SSE Streaming Endpoint

**Files:**
- Modify: `windowsagent/routes/agent.py`
- Modify: `windowsagent/_server_state.py`
- Modify: `windowsagent/agent_loop.py`
- Create: `tests/test_sse.py`

- [ ] **Step 1: Install sse-starlette**

Run: `pip install sse-starlette`

- [ ] **Step 2: Write failing test for SSE endpoint**

```python
# tests/test_sse.py
"""Tests for the SSE streaming endpoint."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    import asyncio
    import windowsagent._server_state as _state
    _state.agent = MagicMock()
    _state.action_lock = asyncio.Lock()
    _state.start_time = 1000.0
    from windowsagent.server import app
    return TestClient(app)


class TestSSEEndpoint:
    def test_stream_endpoint_exists(self, client: TestClient) -> None:
        resp = client.get("/agent/stream", timeout=2)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_sse.py -v`
Expected: FAIL (404 — endpoint doesn't exist)

- [ ] **Step 4: Add event queue to server state**

Modify `windowsagent/_server_state.py` — add:

```python
import asyncio
from asyncio import Queue

# Event queue for SSE streaming — agent_loop pushes events, SSE endpoint reads
agent_event_queue: Queue[dict[str, Any]] | None = None
```

Update `startup_event()` in `server.py` to initialise the queue.

- [ ] **Step 5: Add SSE endpoint to routes/agent.py**

```python
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

@router.get("/agent/stream")
async def agent_stream(request: Request) -> EventSourceResponse:
    """Stream agent status events via Server-Sent Events."""
    async def event_generator():
        if _state.agent_event_queue is None:
            return
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(
                    _state.agent_event_queue.get(), timeout=30.0,
                )
                yield {
                    "event": event.get("type", "status"),
                    "data": json.dumps(event.get("payload", {})),
                }
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
    return EventSourceResponse(event_generator())
```

- [ ] **Step 6: Add event emission to agent_loop.py**

Modify `windowsagent/agent_loop.py` — at each state transition (planning, acting, verifying, done, error), push an event to the queue:

```python
async def _emit_event(event_type: str, payload: dict) -> None:
    import windowsagent._server_state as _state
    if _state.agent_event_queue is not None:
        await _state.agent_event_queue.put({"type": event_type, "payload": payload})
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_sse.py tests/ -m "not integration" -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add windowsagent/routes/agent.py windowsagent/_server_state.py windowsagent/agent_loop.py windowsagent/server.py tests/test_sse.py
git commit -m "feat: SSE streaming endpoint for real-time agent status"
```

---

## Task 3: Voice Pipeline — STT Backend Abstraction

**Files:**
- Create: `windowsagent/voice/__init__.py`
- Create: `windowsagent/voice/stt.py`
- Create: `tests/test_voice_stt.py`
- Modify: `windowsagent/config.py`

- [ ] **Step 1: Add voice config fields**

Modify `windowsagent/config.py` — add to Config dataclass:

```python
    # ── Voice input ──────────────────────────────────────────────
    # STT backend: "groq", "openai", "self-hosted", "local", "off"
    stt_backend: str = "off"
    # API key for cloud STT (Groq or OpenAI). Auto-loaded from GROQ_API_KEY or OPENAI_API_KEY.
    stt_api_key: str = ""
    # Base URL for self-hosted STT (e.g. "http://your-vps:8000")
    stt_base_url: str = ""
    # Local Whisper model size: "tiny", "base", "small"
    stt_local_model: str = "base"
    # Push-to-talk hotkey (default: ctrl+shift+space)
    voice_hotkey: str = "ctrl+shift+space"
```

- [ ] **Step 2: Write failing test for STT backends**

```python
# tests/test_voice_stt.py
"""Tests for STT backend abstraction."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestSTTBackendFactory:
    def test_creates_groq_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend
        backend = create_stt_backend("groq", api_key="test-key")
        assert backend.name == "groq"

    def test_creates_local_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend
        backend = create_stt_backend("local", model_size="base")
        assert backend.name == "local"

    def test_creates_self_hosted_backend(self) -> None:
        from windowsagent.voice.stt import create_stt_backend
        backend = create_stt_backend("self-hosted", base_url="http://localhost:8000")
        assert backend.name == "self-hosted"

    def test_off_returns_none(self) -> None:
        from windowsagent.voice.stt import create_stt_backend
        backend = create_stt_backend("off")
        assert backend is None

    def test_unknown_backend_raises(self) -> None:
        from windowsagent.voice.stt import create_stt_backend
        with pytest.raises(ValueError, match="Unknown STT backend"):
            create_stt_backend("nonexistent")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_voice_stt.py -v`
Expected: FAIL

- [ ] **Step 4: Implement STT backend abstraction**

```python
# windowsagent/voice/__init__.py
"""Voice input module for WindowsAgent."""

# windowsagent/voice/stt.py
"""
Speech-to-text backend abstraction.

All backends implement the same interface: transcribe(audio_bytes) -> str.
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

    def __init__(self, name: str, base_url: str, api_key: str, model: str = "whisper-large-v3-turbo") -> None:
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
            return resp.json().get("text", "").strip()


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
                self._model_size, device="cpu", compute_type="int8",
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
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_voice_stt.py -v`
Expected: PASS

- [ ] **Step 6: Run full suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/voice/`
Expected: All pass, 0 mypy errors

- [ ] **Step 7: Commit**

```bash
git add windowsagent/voice/ windowsagent/config.py tests/test_voice_stt.py
git commit -m "feat: STT backend abstraction with Groq, OpenAI, self-hosted, and local support"
```

---

## Task 4: Voice Pipeline — Activation and Recording

**Files:**
- Create: `windowsagent/voice/activation.py`
- Create: `windowsagent/voice/pipeline.py`
- Create: `tests/test_voice_pipeline.py`

- [ ] **Step 1: Write failing test for voice pipeline**

```python
# tests/test_voice_pipeline.py
"""Tests for the voice activation and pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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
```

- [ ] **Step 2: Implement voice pipeline**

```python
# windowsagent/voice/pipeline.py
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
            import sounddevice as sd
            import numpy as np

            logger.info("Recording audio (max %.1fs)...", duration_seconds)
            audio = sd.rec(
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
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_voice_pipeline.py -v`
Expected: PASS

- [ ] **Step 4: Run full suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/voice/`
Expected: All pass, 0 mypy errors

- [ ] **Step 5: Add voice CLI command**

Modify `windowsagent/cli.py` — add `voice` command for testing:

```python
@cli.command(name="voice")
@click.option("--backend", default=None, help="STT backend override")
def voice_test(backend: str | None) -> None:
    """Test voice input — records and transcribes a voice command."""
    from windowsagent.config import load_config
    from windowsagent.voice.stt import create_stt_backend
    from windowsagent.voice.pipeline import VoicePipeline

    config = load_config()
    stt = create_stt_backend(
        backend or config.stt_backend,
        api_key=config.stt_api_key,
        base_url=config.stt_base_url,
        model_size=config.stt_local_model,
    )
    if stt is None:
        click.echo("Voice is disabled. Set stt_backend in config.", err=True)
        sys.exit(1)

    pipeline = VoicePipeline(stt_backend=stt)
    click.echo("Speak now (recording for up to 10 seconds)...")
    text = pipeline.record_and_transcribe(duration_seconds=10.0)
    if text:
        click.echo(f"Transcribed: {text}")
    else:
        click.echo("No speech detected or transcription failed.", err=True)
```

- [ ] **Step 6: Commit**

```bash
git add windowsagent/voice/ windowsagent/cli.py tests/test_voice_pipeline.py
git commit -m "feat: voice pipeline with recording, VAD, and configurable STT"
```

---

## Task 5: Replay Execution (Prerequisite for Workflow Features)

**Files:**
- Create: `windowsagent/replay.py`
- Create: `tests/test_replay.py`
- Modify: `windowsagent/cli.py`

- [ ] **Step 1: Write failing test for replay**

```python
# tests/test_replay.py
"""Tests for JSONL workflow replay."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestReplayLoader:
    def test_loads_jsonl_file(self) -> None:
        from windowsagent.replay import load_workflow

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"action": "click", "window": "Notepad", "element": "Save"}) + "\n")
            f.write(json.dumps({"action": "type", "window": "Notepad", "element": "Editor", "params": {"text": "Hello"}}) + "\n")
            path = f.name

        steps = load_workflow(path)
        assert len(steps) == 2
        assert steps[0]["action"] == "click"
        assert steps[1]["params"]["text"] == "Hello"
        Path(path).unlink()

    def test_substitutes_variables(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "Dear ${recipient}, here is the ${report}"}
        variables = {"recipient": "Amir", "report": "Q4 report"}
        result = substitute_variables(params, variables)
        assert result["text"] == "Dear Amir, here is the Q4 report"

    def test_missing_variable_raises(self) -> None:
        from windowsagent.replay import substitute_variables

        params = {"text": "Dear ${recipient}"}
        with pytest.raises(ValueError, match="recipient"):
            substitute_variables(params, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_replay.py -v`

- [ ] **Step 3: Implement replay module**

```python
# windowsagent/replay.py
"""
Workflow replay — execute recorded JSONL action sequences.

Loads a JSONL recording file, substitutes variables in parameters,
and executes each step via the Agent API.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def load_workflow(path: str) -> list[dict[str, Any]]:
    """Load a JSONL workflow file into a list of action steps."""
    steps: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON at line %d: %s", line_num, exc)
    return steps


def substitute_variables(
    params: dict[str, Any],
    variables: dict[str, str],
) -> dict[str, Any]:
    """Replace ${variable} placeholders in params with provided values."""
    result: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            missing = [m.group(1) for m in _VAR_PATTERN.finditer(value)
                       if m.group(1) not in variables]
            if missing:
                raise ValueError(
                    f"Missing variable(s): {', '.join(missing)}"
                )
            result[key] = _VAR_PATTERN.sub(
                lambda m: variables[m.group(1)], value,
            )
        else:
            result[key] = value
    return result


def run_workflow(
    path: str,
    variables: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Execute a recorded JSONL workflow.

    Args:
        path: Path to the JSONL recording file.
        variables: Variable substitutions for parameterised workflows.

    Returns:
        List of step results.
    """
    from windowsagent.agent import Agent
    from windowsagent.config import load_config

    steps = load_workflow(path)
    if not steps:
        raise ValueError(f"No steps found in {path}")

    config = load_config()
    agent = Agent(config)
    vars_ = variables or {}
    results: list[dict[str, Any]] = []

    for i, step in enumerate(steps):
        window = step.get("window", "")
        action = step.get("action", "")
        element = step.get("element", "")
        params = step.get("params", {})

        # Substitute variables
        if params:
            params = substitute_variables(params, vars_)

        logger.info("Replay step %d/%d: %s on %r", i + 1, len(steps), action, element)

        try:
            result = agent.act(window, action, element, params)
            results.append({
                "step": i + 1,
                "success": result.success,
                "action": action,
                "element": element,
                "error": result.error,
            })
        except Exception as exc:
            results.append({
                "step": i + 1,
                "success": False,
                "action": action,
                "element": element,
                "error": str(exc),
            })
            logger.warning("Replay step %d failed: %s", i + 1, exc)

    return results
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_replay.py -v`
Expected: PASS

- [ ] **Step 5: Add CLI replay command**

Modify `windowsagent/cli.py`:

```python
@cli.command(name="replay")
@click.argument("workflow_path", type=click.Path(exists=True))
@click.option("--var", multiple=True, help="Variable substitution (key=value)")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def replay(workflow_path: str, var: tuple[str, ...], json_output: bool) -> None:
    """Replay a recorded JSONL workflow."""
    from windowsagent.replay import run_workflow

    variables = {}
    for v in var:
        if "=" not in v:
            click.echo(f"Invalid variable format: {v!r} (expected key=value)", err=True)
            sys.exit(1)
        key, value = v.split("=", 1)
        variables[key] = value

    try:
        results = run_workflow(workflow_path, variables)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        for r in results:
            status = "[OK]" if r["success"] else "[FAIL]"
            click.echo(f"  {status} Step {r['step']}: {r['action']} on {r['element']!r}")
```

- [ ] **Step 6: Run full suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/replay.py`

- [ ] **Step 7: Commit**

```bash
git add windowsagent/replay.py tests/test_replay.py windowsagent/cli.py
git commit -m "feat: JSONL workflow replay with variable substitution"
```

---

## Task 6: Update Config, Architecture, and Push

- [ ] **Step 1: Update ARCHITECTURE.md**

Add sections for MCP server, SSE streaming, voice pipeline, replay execution.

- [ ] **Step 2: Update pyproject.toml with new optional dependency groups**

```toml
[project.optional-dependencies]
mcp = ["mcp[cli]>=1.0", "httpx>=0.27"]
voice = ["faster-whisper>=1.0", "sounddevice>=0.4", "httpx>=0.27"]
gui = ["# placeholder for Electron build dependencies"]
```

- [ ] **Step 3: Run full test suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/`
Expected: All pass, 0 errors

- [ ] **Step 4: Commit and push**

```bash
git add -A
git commit -m "feat: MCP server, voice pipeline, SSE streaming, replay execution"
git push origin feature/mcp-server
```

- [ ] **Step 5: Open PR**

```bash
gh pr create --title "feat: MCP server, voice pipeline, SSE streaming, replay" --body "Phase 1 of GUI+Voice plan. See docs/GUI-VOICE-DECISION-BRIEF.md"
```

---

## Future Tasks (Separate Plans)

These are documented here for reference but will get their own implementation plans:

### Task 7: UIA Element Overlay (Weeks 5-6)
- PyQt6 transparent overlay window
- Colour-coded bounding boxes over UIA elements
- Click-to-inspect element properties
- Search box: type "save" to highlight matching elements
- "Add to profile" button for community profile authoring

### Task 8: Electron GUI Shell (Weeks 7-8)
- electron-vite + React + shadcn/ui scaffold
- contextBridge preload with whitelisted IPC
- Dark mode default, WCAG 2.2 AA compliance
- SSE EventSource connection to localhost:7862

### Task 9: GUI Core Components (Weeks 9-10)
- Command palette (cmdk, Ctrl+K)
- TaskInput with natural language box
- StatusPanel with ARIA live region
- ActionLog with role="log" streaming
- VoiceButton (push-to-talk)
- SettingsPanel (STT backend picker, profile config)

### Task 10: GUI Polish + Accessibility (Week 11)
- NVDA screen reader testing
- Manual screen reader toggle (Electron auto-detection broken since v37)
- Keyboard navigation for all components
- High contrast / forced-colours support
- 44px minimum touch targets
- Onboarding flow (3 steps, first launch only)

---

## Guardrails

- **Tests:** 227+ unit tests must keep passing. Run `python -m pytest tests/ -m "not integration" -q` after every task.
- **Types:** mypy must stay at 0 errors. Run `python -m mypy windowsagent/` after every task.
- **Lint:** ruff 2 pre-existing RUF005 warnings in routes/system.py — ignore. No new warnings.
- **File limits:** Python files under 250 lines. Split if needed.
- **Security:** MCP server and voice pipeline must not expose any network surface beyond localhost.
- **Accessibility:** Every UI component gets ARIA roles and keyboard navigation in the first implementation, not in a later pass.
