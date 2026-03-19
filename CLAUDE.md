# WindowsAgent — Project Rules

## Project Overview

Windows desktop automation tool — controls apps via the Windows UI Automation accessibility tree, with vision LLM fallback. Must work on any Windows 10/11 system regardless of DPI, monitor setup, or locale.

### Key References

- **ARCHITECTURE.md** — authoritative design doc, component specs, data flow diagrams. Read before making architectural changes.
- **CONVERSATION-HANDOFF.md** — current state, open PRs, next priorities. Read at session start.
- **docs/superpowers/plans/** — implementation plans. Check for active plans before starting new features.
- **docs/GUI-VOICE-DECISION-BRIEF.md** — deep research behind GUI/voice/MCP decisions.

### Setup

```bash
pip install -e ".[vision,mcp,voice,overlay,browser]"  # Full install
pip install -e "."                                      # Core only
```

Optional dependency groups: `vision` (Gemini/Claude), `mcp` (MCP server), `voice` (STT backends), `overlay` (PyQt6), `browser` (Playwright CDP), `ocr` (Tesseract).

## Architectural Principles

1. **UIA-first, always.** Accessibility tree before vision API. Vision models hallucinate; UIA gives exact names and positions.
2. **Verify every action.** Every `act()` is followed by `verify()`. If state didn't change, retry or escalate.
3. **App profiles encapsulate quirks.** Each app with known UIA oddities gets a profile in `apps/`. Generic fallback for unknown apps.
4. **Fail loudly.** Typed exceptions, never swallow errors, log everything.
5. **Config drives everything.** No hardcoded timeouts, model names, or retry counts.

## Module Map

| Area | Where | What |
|------|-------|------|
| Agent loop | `agent.py`, `agent_loop.py`, `agent_types.py` | Observe-Plan-Act-Verify orchestration |
| Observation | `observer/` | UIA tree (`uia.py`), screenshots, OCR, state capture |
| Grounding | `grounder/` | Find elements by description — UIA first, vision fallback |
| Actions | `actor/` | UIA patterns (`uia_actor.py`), coordinate input, clipboard |
| Verification | `verifier/verify.py` | Screenshot diff, element change detection |
| App profiles | `apps/` + `apps/community/` | Per-app quirks, known elements, strategies |
| HTTP API | `server.py`, `routes/` | FastAPI on localhost:7862 |
| CLI | `cli.py` | Click CLI — windows, observe, act, serve, mcp, voice, replay, overlay |
| MCP | `mcp_server.py` | FastMCP stdio server, proxies to HTTP API |
| Overlay | `overlay/` | PyQt6 transparent bounding box visualisation |
| Voice | `voice/` | STT backend abstraction + recording pipeline |
| Recovery | `recovery.py` | Circuit breaker, focus recovery, dialog detection |

## Common Commands

```bash
pytest tests/ -m "not integration" -q   # Unit tests
mypy windowsagent/                       # Type checking (0 errors required)
ruff check windowsagent/                 # Lint (ignore 2 pre-existing RUF005 in routes/system.py)
windowsagent serve                       # Start server (required for overlay + integration tests)
windowsagent overlay --window "Notepad"  # Launch UIA overlay
```

## Git Workflow

- Small fix / docs: commit + push to `main`
- Feature touching 3+ files: branch (`feature/short-name`), commit, push, open PR
- Risky refactor: branch (`fix/short-name`), commit, push, open PR with risk explanation
- Always push after committing unless explicitly WIP

## Testing: Real Evidence Only

**No mock-based guesses.** Every test must model real program usage with tangible evidence.

### Evidence hierarchy

1. **Screenshot** — visual proof output matches expectations
2. **Real API response** — captured from running server, compared
3. **File output** — generated files verified against expected content
4. **CLI output** — command output checked against expected format
5. **Mock with verified shape** — LAST RESORT. Must include comment: `# Mock shape verified against real API on YYYY-MM-DD` explaining why mock is needed

### Rules

- "The test passes" is not evidence. "The test produces X which matches Y" is evidence.
- If the real API shape changes, all mocks using that shape must be updated in the same commit.
- Integration tests (`@pytest.mark.integration`) hit real Windows apps — these are the gold standard.

## Security Model

- Server binds `127.0.0.1` ONLY. Warn loudly if changed.
- No credentials in code — API keys via environment variables or config file
- Action classification: Tier 1 (safe, no confirm), Tier 2 (sensitive, confirm if enabled), Tier 3 (blocked — UAC, password fields)
- No OWASP top 10 vulnerabilities

## Accessibility

- Target: WCAG 2.2 AA for all UI components
- 44px minimum touch targets
- ARIA roles and keyboard navigation in first implementation, not later
- Position as "desktop automation" not "accessibility tool" until tested with disabled users

## Brand & Design

### Brand Colour Palette (from Small Giants Studio logo)

| Token | Hex | Use |
|-------|-----|-----|
| `--brand-teal-dark` | `#0A6B6E` | Headers, primary text on dark backgrounds |
| `--brand-teal` | `#118795` | Primary actions, focus states, links |
| `--brand-teal-light` | `#7EC8C8` | Hover states, subtle accents, borders |
| `--brand-orange` | `#FC7908` | Active element, CTAs, "you are here" indicator |
| `--bg-dark` | `#121418` | App background (warm-shifted, not pure black) |
| `--surface` | `#1C1F24` | Cards, palette background, panels |
| `--surface-hover` | `#252830` | Hover states on surfaces |

All colour pairs must pass WCAG 2.2 AA contrast (4.5:1 text, 3:1 UI components). The teal-orange pair is CVD-safe (verified).

### Design Personality

**"Capable, Warm, Responsive"** — not clinical like VS Code, not playful like a game. An agent that acts on your behalf should feel trustworthy and alive.

- **Direction:** Warm Modern (Linear/Notion aesthetic, not VS Code/Raycast instrument feel)
- **Theme:** Dark mode default (82% preference for AI-heavy apps). Light mode available
- **Logo gradient:** The teal dark-to-light gradient from the SGS logo is a brand element. Use as subtle background accents, not loud gradients
- **Typography:** Segoe UI (Windows system font) for UI. Monospace for code/values

### Anti-References (do NOT look like these)

- Power Automate — cluttered enterprise flowcharts
- VS Code — soulless instrument, too clinical
- Chatbot UIs — no avatar, no "thinking..." bubbles, no conversation threading
- Gaming/neon — no glow effects, no gradients-for-the-sake-of-it

### Design Principles

1. **Keyboard is the moat.** Every action reachable via keyboard. Command palette is the primary interface
2. **Two levels max.** Progressive disclosure: Layer 1 = palette + status. Layer 2 = inspector + advanced. No deeper (NN/G guidance)
3. **Show, don't tell.** Pre-populate suggestions instead of empty states. The UI should always show what's possible
4. **Alive, not animated.** Subtle transitions that communicate state changes (idle/running/done). No decorative motion. Respect `prefers-reduced-motion`
5. **Trust through transparency.** Show what the agent is doing in real time (SSE status strip). Users trust what they can see

### Overlay-Specific Design

- **Overlay palette:** IBM CVD-safe default. 5 functional groups (Interactive, Text Input, Container, Navigation, Other)
- **Overlay style:** Borders not fills. 2-4px with style differentiation (solid/dashed/dotted)
- **Active element:** Brand orange `#FC7908` thick border for "agent is working on this now"
- **Presets:** Ship 3 — Default (CVD-safe), High Contrast, Monochrome

## Code Standards

- Python files: 250 lines maximum — split into focused modules
- PyQt6 imports behind `try/except ImportError` — pure functions must work without PyQt6
- Overlay fetches UIA data via HTTP API only — process isolation from agent server
- External libs without type stubs (pywinauto, pyautogui, PIL) typed as `Any` not `object`
- `from __future__ import annotations` in every file

## Common Mistakes

- **Don't mock API responses without checking the real shape first.** The `/observe` endpoint shape is not what you'd guess.
- **Don't assume primary monitor.** Target windows can be on any display. Detect the correct screen.
- **Don't use fills for overlay bounding boxes.** Borders only — fills obscure the app underneath.
- **Don't add colours per UIA control type.** Group into 5 functional categories instead.
- **Don't skip the handoff.** Update CONVERSATION-HANDOFF.md at session end. Use `/handoff`.
