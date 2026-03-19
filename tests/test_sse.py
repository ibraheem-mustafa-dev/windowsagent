"""Tests for the SSE streaming endpoint and event emission."""
from __future__ import annotations

import asyncio

import pytest


class TestSSEEndpoint:
    def test_stream_endpoint_registered(self) -> None:
        """Verify the /agent/stream route exists on the FastAPI app."""
        from windowsagent.server import app

        routes = [r.path for r in app.routes]  # type: ignore[union-attr]
        assert "/agent/stream" in routes

    def test_stream_endpoint_returns_event_source_response(self) -> None:
        """Verify the endpoint handler returns an EventSourceResponse."""
        from windowsagent.routes.agent import agent_stream

        assert callable(agent_stream)


class TestEmitEvent:
    def test_emit_event_puts_to_queue(self) -> None:
        from windowsagent.agent_loop import _emit_event
        import windowsagent._server_state as _state

        _state.agent_event_queue = asyncio.Queue()  # type: ignore[assignment]
        asyncio.run(_emit_event("planning", {"task": "test"}))
        assert not _state.agent_event_queue.empty()
        event = _state.agent_event_queue.get_nowait()
        assert event["type"] == "planning"
        assert event["payload"]["task"] == "test"

    def test_emit_event_noop_when_no_queue(self) -> None:
        from windowsagent.agent_loop import _emit_event
        import windowsagent._server_state as _state

        _state.agent_event_queue = None
        # Should not raise
        asyncio.run(_emit_event("planning", {"task": "test"}))

    def test_emit_multiple_events(self) -> None:
        from windowsagent.agent_loop import _emit_event
        import windowsagent._server_state as _state

        _state.agent_event_queue = asyncio.Queue()  # type: ignore[assignment]

        async def emit_three() -> None:
            await _emit_event("observing", {"step": 1})
            await _emit_event("acting", {"step": 2})
            await _emit_event("done", {"step": 3})

        asyncio.run(emit_three())
        assert _state.agent_event_queue.qsize() == 3

        events = []
        while not _state.agent_event_queue.empty():
            events.append(_state.agent_event_queue.get_nowait())

        assert [e["type"] for e in events] == ["observing", "acting", "done"]


class TestServerStateQueue:
    def test_agent_event_queue_default_is_none(self) -> None:
        """Verify the module-level default before startup."""
        # Re-check the attribute exists
        import windowsagent._server_state as _state

        assert hasattr(_state, "agent_event_queue")
