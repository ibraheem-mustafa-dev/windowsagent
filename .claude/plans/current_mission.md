# WindowsAgent Gap Analysis & Remediation Plan

**Date:** 2026-03-18
**Status:** Phase 1 (pywinctl integration) COMPLETE. Remaining gaps documented below.
**Scope:** Full gap analysis (code vs spec, spec vs optimal), pywinctl reintegration, architecture review

---

## Dependency Status (Key Finding)

| Library | In pyproject.toml | Actually Used | Status |
|---------|------------------|---------------|--------|
| **pywinauto** | Yes (>=0.6.8) | Yes — 6+ files, core of UIA tree | OK |
| **pyautogui** | Yes (>=0.9.54) | Yes — input_actor.py, screenshot.py | OK |
| **pywinctl** | Yes (>=0.4) | **NO — zero imports, zero usage** | DEAD DEPENDENCY |
| mss | Yes (>=9.0) | Yes — screenshot.py (primary) | OK |
| pywin32 | Yes (>=306) | Yes — clipboard, window enum, DPI | OK |
| Pillow | Yes (>=10.0) | Yes — image manipulation | OK |
| psutil | Yes (>=5.9) | Yes — process info | OK |

**pywinctl is declared as a dependency but never used anywhere in the codebase.** It should be providing window management operations (activate, minimise, maximise, resize, move, get geometry) that are currently either missing or handled through lower-level ctypes/pywinauto calls.

---

## GAP ANALYSIS 1: Current Code vs Spec

### Phase 1 Gaps (Foundation)

| Spec Requirement | Code Status | Gap Severity |
|-----------------|-------------|--------------|
| UIA tree inspection | DONE | None |
| Screenshot capture (mss) | DONE | None |
| OCR extraction | DONE | None |
| UIA action execution | DONE | None |
| pyautogui fallback | DONE | None |
| Win32 clipboard | DONE | None |
| Notepad profile | DONE | None |
| File Explorer profile | DONE | None |
| Outlook profile | DONE | None |
| Calculator integration test | **MISSING** | Low — not in profiles |
| HTTP API (all endpoints) | DONE (FastAPI) | None |
| CLI interface | DONE | None |
| Window activation/management via pywinctl | **MISSING** | **HIGH** — core window ops missing |
| DPI scaling at 100% + 150% | Partial — code exists, untested at 150% | Medium |

### Phase 2 Gaps (Production Reliability + S-Grade)

| Spec Requirement | Code Status | Gap Severity |
|-----------------|-------------|--------------|
| LLM task planner (Gemini/Claude) | DONE | None |
| Agent.run() observe-plan-act-verify | DONE | None |
| Action recording (JSONL) | DONE | None |
| Browser grounding (CDP) | DONE | None |
| WebView2 scroll handling | DONE | None |
| Excel cell read/write via Name Box | **MISSING** | **HIGH** — spec requires it |
| Excel app profile | **MISSING** | **HIGH** — spec requires it |
| Vision fallback when UIA empty | DONE | None |
| DPI scaling tested at 100% + 150% | **UNTESTED** | Medium |
| Agent Replay Videos (--record → .mp4 + .gif) | **MISSING** | **HIGH** — S-grade feature |
| Community App Profiles system (profiles/community/) | **MISSING** | **HIGH** — S-grade feature |
| CONTRIBUTING.md golden path | **MISSING** | Medium |
| At least 2 community profiles merged | **MISSING** | Medium |

### Phase 3 Gaps (Intelligent Automation + Plugins)

| Spec Requirement | Code Status | Gap Severity |
|-----------------|-------------|--------------|
| Error recovery (focus loss, unexpected dialogs) | **MISSING** | **CRITICAL** |
| Plugin system (5 hooks) | **MISSING** | **HIGH** |
| Plugin manifest JSON | **MISSING** | HIGH |
| MCP server for Claude Desktop/Cursor | **MISSING** | HIGH |
| Replay JSONL with variable substitution | **MISSING** | HIGH |
| 80%+ task success rate | **UNTESTED** | Medium |

### Cross-Cutting Gaps

| Area | Gap | Severity |
|------|-----|----------|
| **pywinctl integration** | Zero usage despite being a core dependency | **CRITICAL** |
| **Window management** | No activate/minimise/maximise/resize/move API | **HIGH** |
| **Test coverage** | ~25-30% effective coverage; 10+ modules untested | **HIGH** |
| **OCR tests** | Entire ocr.py module untested | Medium |
| **Vision grounder tests** | Entire vision_grounder.py untested | Medium |
| **input_actor tests** | Core functions have zero unit tests | **HIGH** |
| **server.py tests** | All endpoints untested | **HIGH** |
| **agent.py tests** | Main orchestrator untested | **HIGH** |
| **File length** | server.py is 600 lines (limit: 250) | Medium |
| **File length** | agent.py is 480 lines (limit: 250) | Medium |
| **File length** | uia.py is 450 lines (limit: 250) | Medium |
| **File length** | screenshot.py is 420 lines (limit: 250) | Medium |

---

## GAP ANALYSIS 2: Spec vs Optimal (What the Spec Should Be)

### Phase 1 Spec Gaps

| Stated Goal | Spec Says | Optimal Approach | Gap |
|-------------|-----------|-----------------|-----|
| **Window management** | Mentions pywinctl in deps | Should specify a WindowManager abstraction over pywinctl for: activate, minimise, maximise, resize, move, get_geometry, is_visible, bring_to_front, get_all_by_pid | Spec lists pywinctl as dependency but never defines how it should be used |
| **Multi-monitor** | "Phase 1: single monitor only" | Should support multi-monitor from day 1 — mss already does, just need monitor-aware coordinate mapping | Artificial limitation; the code already handles it |
| **Retry strategy** | "3 retries" | Should specify exponential backoff with jitter, not fixed retries — prevents thundering herd on shared apps | Too simplistic |
| **Concurrent access** | Not mentioned | Should specify thread-safety model from Phase 1 — multiple callers via HTTP API is the primary use case | Missing from spec |

### Phase 2 Spec Gaps

| Stated Goal | Spec Says | Optimal Approach | Gap |
|-------------|-----------|-----------------|-----|
| **Replay Videos** | ffmpeg .mp4 + .gif generation | Should use native Python (moviepy or imageio) to avoid ffmpeg dependency. ffmpeg is a system install — friction for pip users | External dependency not in pip |
| **Community Profiles** | CONTRIBUTING.md + auto-merge | Should include: profile testing framework (mock UIA trees per app), version compatibility matrix, and automated screenshot comparison for profile changes | Testing story incomplete |
| **Excel support** | "Name Box cell addressing" | Should also support: formula bar, cell range selection, sheet tabs, data validation dropdowns. Name Box alone is fragile | Underspecified |
| **Browser grounding** | CDP AX tree + DOM | Should specify: tab management (switch tabs, close tabs, list tabs), cookie/session handling, download management, popup handling | Underspecified for real-world browser automation |

### Phase 3 Spec Gaps

| Stated Goal | Spec Says | Optimal Approach | Gap |
|-------------|-----------|-----------------|-----|
| **Error recovery** | 3-tier handling (retry → user → abort) | Should include: state checkpointing (save/restore), undo capability (reverse last N actions), and circuit breaker pattern (stop after N consecutive failures, not just per-step) | No undo/checkpoint concept |
| **Plugin system** | 5 hooks, manifest JSON | Should specify: plugin sandboxing (subprocess isolation), resource limits, error isolation (plugin crash doesn't kill agent), hot-reload during task | Security and reliability underspecified |
| **MCP server** | "for Claude Desktop/Cursor" | Should specify: which MCP resources/tools to expose, how to handle MCP tool timeouts (agent actions are slow), streaming progress updates | Interface contract missing |
| **Task success rate** | "80%+" | Should define: what counts as success (task complete? partial? element found?), standardised benchmark suite (not ad-hoc), regression tracking across versions | Success criteria vague |

### Phase 4 Spec Gaps

| Stated Goal | Spec Says | Optimal Approach | Gap |
|-------------|-----------|-----------------|-----|
| **Record-and-replay** | 6-level selector chain | Should also record: window z-order, focus state, clipboard contents, and timing between actions — all needed for reliable replay | State capture incomplete |
| **NL Workflow Editor** | "LLM modifies JSON" | Should use structured output (tool_use/function_calling) not raw JSON parsing — current approach is fragile with LLM hallucinations | Fragile LLM integration |
| **Marketplace** | Stripe Connect, 0% then 10% | Should also specify: workflow sandboxing (untrusted code from marketplace), malware scanning, review queue, and liability model | Security gap for untrusted workflows |

### Architecture-Level Spec Gaps

| Area | What's Missing | Impact |
|------|---------------|--------|
| **Window lifecycle management** | No spec for window activation, focus management, z-order control via pywinctl | Actions fail when target window isn't foreground |
| **Session management** | No concept of "agent session" — each API call is stateless | Can't track multi-call workflows, can't resume after crash |
| **Observability** | No structured logging spec, no metrics, no tracing | Can't debug failures in production, can't measure success rates |
| **Rate limiting** | No spec for action pacing per app | Fast actions break apps (especially Outlook, Teams) |
| **Graceful shutdown** | No spec for what happens when server stops mid-task | Tasks left in unknown state |
| **Health monitoring** | /health exists but doesn't check dependencies (pywinauto, mss, CDP) | Can report healthy when actually broken |

---

## REMEDIATION PLAN

### Priority 1: pywinctl Integration (CRITICAL)

pywinctl should provide the window management layer that sits between the agent and the OS. Currently, window activation is scattered across ctypes calls and pywinauto. A clean `WindowManager` using pywinctl would consolidate this.

**What pywinctl provides that's currently missing or fragmented:**
1. `activate()` / `focus()` — bring window to foreground reliably
2. `minimize()` / `maximize()` / `restore()` — window state control
3. `resize()` / `moveTo()` — window positioning for multi-monitor
4. `getWindowRect()` — reliable geometry without ctypes
5. `isVisible()` / `isMinimized()` / `isMaximized()` — state queries
6. `getAllWindows()` / `getWindowsWithTitle()` — window enumeration
7. Cross-platform potential (pywinctl works on macOS/Linux too)

**Integration points:**
- `observer/uia.py` — replace manual win32gui.EnumWindows with pywinctl for window listing
- `actor/uia_actor.py` — use pywinctl.activate() before actions instead of ctypes SetForegroundWindow
- `agent.py` — window lifecycle (activate before observe, restore after task)
- `server.py` — new `/window/manage` endpoint for activate/minimise/maximise
- New `windowsagent/window_manager.py` module

### Priority 2: Missing Phase 2 Features

1. **Excel app profile** — Name Box addressing, formula bar, sheet tabs
2. **Community profiles system** — profiles/community/ structure, _template, meta YAML, auto-discovery

### Priority 3: Test Coverage

Raise from ~25% to 60%+ by testing the 10 untested modules:
1. input_actor.py — core input functions
2. agent.py — main orchestrator
3. server.py — FastAPI endpoints
4. vision_grounder.py — LLM vision
5. ocr.py — text extraction
6. browser/launcher.py — Chrome launch
7. recorder.py — JSONL recording
8. cli.py — CLI commands
9. Remaining app profiles

### Priority 4: File Length Compliance

Split oversized files:
- server.py (600 lines) → server.py + routes/browser.py + routes/agent.py
- agent.py (480 lines) → agent.py + agent_loop.py
- uia.py (450 lines) → uia.py + uia_cache.py + uia_search.py
- screenshot.py (420 lines) → screenshot.py + screenshot_backends.py

### Priority 5: Phase 3 Foundations

1. Error recovery framework (focus loss, unexpected dialogs)
2. Plugin hook system (on_observe, on_act minimum)
3. MCP server skeleton

---

## IMPLEMENTATION ORDER

1. ~~Create `windowsagent/window_manager.py` using pywinctl~~ DONE
2. ~~Integrate window_manager into actor/uia_actor.py, agent.py~~ DONE
3. ~~Add window management endpoints to server.py~~ DONE (POST /window/manage)
4. ~~Write tests for window_manager~~ DONE (28 unit tests, all pass)
5. ~~Add CLI `windowsagent window` command~~ DONE
6. ~~Update ARCHITECTURE.md~~ DONE (v0.4.0)
7. ~~Wire profile strategies into agent loop~~ DONE (_execute_scroll, _execute_type, focus restore)
8. ~~Flesh out OutlookProfile~~ DONE (34 known_elements, 18 shortcuts, clipboard strategy, on_before_act)
9. ~~Write profile dispatch tests~~ DONE (38 tests, all pass)
10. ~~Create Excel app profile~~ DONE (excel.py, 22 tests)
11. Set up community profiles structure
12. ~~Split oversized files (server.py, agent.py, uia.py, screenshot.py)~~ DONE (server.py 98, agent.py 266, uia.py 222, screenshot.py 240)
13. Write missing tests (priority: input_actor, agent, server)
14. ~~Error recovery framework~~ DONE (recovery.py, 16 tests, wired into agent_loop.py)
15. Plugin hooks skeleton
