# Session Handoff — 2026-03-19

## Completed This Session

1. **Excel profile verified against live Excel** -- Launched Excel (Microsoft 365, UK English), walked UIA tree with pywinauto. Found 6 mismatches: Formula Bar and sheet tabs not exposed as UIA elements, button names locale-dependent (Font Colour, Centre, AutoSum, Sort & Filter). Added US English aliases. Updated windowsagent/apps/excel.py and tests/test_profile_dispatch.py.
2. **Community profiles auto-discovery system** -- Created windowsagent/apps/community/ with __init__.py (pkgutil + inspect discovery), _template.py, _template_meta.yml, CONTRIBUTING.md. Updated apps/__init__.py to insert community profiles before GenericAppProfile.
3. **Test coverage push: 161 to 227 tests (+66)** -- New test files: test_input_actor.py (21), test_server.py (18), test_cli.py (19), test_community_profiles.py (8). All mock dependencies to avoid real UI interactions.
4. **PR #2 merged to main** -- feature/window-manager-profile-wiring merged via gh pr merge. Main branch contains all v0.5.0 + v0.5.1 work.
5. **Deep research: GUI + Voice + MCP architecture** -- 8 parallel research agents, 100+ sources, covering GUI frameworks, voice pipelines, accessibility requirements, power user needs, competitive landscape. Full findings in docs/GUI-VOICE-DECISION-BRIEF.md.
6. **Implementation plan written** -- Complete TDD plan with 6 tasks, exact code, file paths, and test commands in docs/superpowers/plans/2026-03-18-gui-voice-mcp.md.
7. **ARCHITECTURE.md updated to v0.5.1** -- Added Phase 3 priorities, updated tech debt, development focus section.

## Current State

- **Branch:** main at 416b542
- **Tests:** 227 pass, 0 fail (unit only; integration tests skipped)
- **Build:** mypy 0 errors, ruff 2 pre-existing RUF005 warnings (ignorable)
- **Uncommitted changes:** none (switch_and_search.py and test_ocr.py are scratch files, intentionally untracked)

## Known Issues / Blockers

- **routes/window.py HTTPException bug** -- broad `except Exception` catches HTTPException(400) for unknown actions and re-wraps as 500. Low priority.
- **agent.py is 266 lines** -- 16 over limit. act() is inherently complex. Not worth splitting without agent.py tests first.

## Next Priorities (in order)

1. **MCP server** -- Task 1 in the plan. Create windowsagent/mcp_server.py wrapping existing FastAPI endpoints via FastMCP stdio transport. Install mcp[cli] and httpx. Add CLI entry point. 1 week.
2. **SSE streaming endpoint** -- Task 2 in the plan. Add GET /agent/stream using sse-starlette, event queue in _server_state, emit events from agent_loop.py. Can run parallel with Task 1.
3. **Voice pipeline** -- Tasks 3-4 in the plan. STT backend abstraction (Groq/OpenAI/self-hosted/local) + recording pipeline with sounddevice + silero-vad. 2-3 weeks.
4. **JSONL replay execution** -- Task 5 in the plan. Load recorded JSONL, substitute variables, execute via Agent.act(). 1 week.
5. **Electron GUI** -- Tasks 7-10 in the plan (separate future plan). React + shadcn/ui + Radix + cmdk. 4 weeks.

## Files Modified

| File | What changed |
|------|-------------|
| windowsagent/apps/excel.py | Verified against live Excel, corrected UK locale names, added US aliases |
| windowsagent/apps/__init__.py | Added community profile auto-discovery |
| windowsagent/apps/community/__init__.py | NEW -- discover_profiles() auto-discovery |
| windowsagent/apps/community/_template.py | NEW -- documented BaseAppProfile template |
| windowsagent/apps/community/_template_meta.yml | NEW -- metadata template |
| windowsagent/apps/community/CONTRIBUTING.md | NEW -- contributor guide |
| tests/test_input_actor.py | NEW -- 21 tests for input_actor.py |
| tests/test_server.py | NEW -- 18 tests for HTTP endpoints |
| tests/test_cli.py | NEW -- 19 tests for CLI commands |
| tests/test_community_profiles.py | NEW -- 8 tests for auto-discovery |
| tests/test_profile_dispatch.py | Updated Excel formula bar test |
| ARCHITECTURE.md | Updated to v0.5.1 with Phase 3 priorities |
| .claude/plans/current_mission.md | Steps 11, 13 marked complete |
| docs/GUI-VOICE-DECISION-BRIEF.md | NEW -- full research findings |
| docs/superpowers/plans/2026-03-18-gui-voice-mcp.md | NEW -- implementation plan |
| docs/WindowsAgent-GUI-Voice-Brief.pdf | NEW -- ADHD-friendly PDF brief |

## Notes for Next Session

- **Electron chosen over Tauri** because Tauri has an unresolved NVDA screen reader regression (Issue #12901). pywebview ruled out entirely (NVDA broken, Issue #545). PyQt6 has Qt-level screen reader bugs.
- **openWakeWord over Porcupine** -- Porcupine's free tier caps at 3 monthly active users, then $6K/year. openWakeWord is Apache 2.0 with no MAU cap.
- **Voice is secondary, keyboard is primary** -- standard Whisper has 50-80% WER for dysarthric speech. Position as "desktop automation with keyboard and voice options", not "accessibility tool", until tested with disabled users.
- **STT backend is configurable** -- users choose Groq API (fast), OpenAI, self-hosted Speaches on VPS, or local faster-whisper. All use the same OpenAI-compatible API format.
- **CLI test patching** -- CLI functions use lazy imports inside function bodies. Patches must target source modules (e.g. windowsagent.observer.uia.get_windows), not the CLI module.

## Next Session Prompt

~~~
Invoke `/superpowers:using-superpowers` before doing anything else.

Read CONVERSATION-HANDOFF.md and docs/superpowers/plans/2026-03-18-gui-voice-mcp.md for full context. The plan has exact code, file paths, and test commands for each task. Execute it.

## Skills to Invoke

| Skill | When to use |
|-------|-------------|
| `/superpowers:using-superpowers` | FIRST -- before any response, establishes live skill routing |
| `/superpowers:executing-plans` | Execute the plan in docs/superpowers/plans/2026-03-18-gui-voice-mcp.md task by task |
| `/superpowers:test-driven-development` | Each task -- write tests before implementation |
| `/superpowers:verification-before-completion` | After each task -- run tests before claiming done |

## MCP Servers & Tools

| Tool | What to use it for |
|------|-------------------|
| `context7` (resolve-library-id, get-library-docs) | Look up FastMCP, sse-starlette, and faster-whisper docs before implementing |
| `github` MCP | Check for open issues on mcp python package if integration problems arise |

## Agents to Delegate To

| Agent | When |
|-------|------|
| `test-and-explain` | After Task 1 (MCP server) -- verify and explain what's covered |
| `feature-dev:code-reviewer` | After Tasks 1-2 -- check MCP + SSE integration doesn't break existing endpoints |

---

## Task 1: MCP Server (Task 1 in plan)

Follow docs/superpowers/plans/2026-03-18-gui-voice-mcp.md Task 1 exactly. Create windowsagent/mcp_server.py with FastMCP wrapping existing FastAPI endpoints. Install mcp[cli] and httpx. Add CLI entry point. Write tests first. Create feature branch.

## Task 2: SSE Streaming (Task 2 in plan)

Follow the plan Task 2. Add GET /agent/stream SSE endpoint using sse-starlette. Add event queue to _server_state.py. Emit events from agent_loop.py at state transitions. Write tests first.

## Task 3: Voice Pipeline STT Backend (Task 3 in plan)

Follow the plan Task 3. Create windowsagent/voice/stt.py with OpenAICompatibleSTT and LocalWhisperSTT backends. Add voice config fields to config.py. The factory function create_stt_backend() supports groq, openai, self-hosted, local, and off. Write tests first.

## Guardrails

227 unit tests must keep passing. Run `python -m pytest tests/ -m "not integration" -q` after each task. mypy must stay at 0 errors. The 2 RUF005 warnings in routes/system.py are pre-existing -- ignore them. Create a feature branch before writing code.
~~~
