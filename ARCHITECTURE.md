# WindowsAgent — Architecture Reference

**Version:** 0.6.1 (UIA element overlay)
**Date:** 2026-03-19
**Status:** Authoritative design document. All modules must conform to this spec.

**Changelog (0.6.1):**
- `overlay/__init__.py` -- New package. Exports OverlayWindow, InspectorPanel, launch_overlay.
- `overlay/renderer.py` -- New. Colour mapping (5 functional groups from IBM CVD-safe palette), UIA tree flattening, DPI scaling, HTTP fetch from localhost:7862, OverlayWindow launcher. Pure functions separated from PyQt6 for testability.
- `overlay/widget.py` -- New. OverlayWidget (QWidget): transparent frameless always-on-top window, QPainter bounding box drawing (borders only, no fills), click-to-inspect, keyboard shortcuts (Escape=quit, F=search, R=refresh).
- `overlay/inspector.py` -- New. InspectorPanel: element property display, search filtering (dims non-matches), "Add to profile" code generation for community profile authoring.
- `cli.py` -- Added `overlay` command: `windowsagent overlay --window "Title" [--port PORT]`.
- `pyproject.toml` -- Added `overlay` optional dependency group (PyQt6>=6.5).
- `tests/test_overlay.py` -- New. 21 unit tests: colour mapping, tree flattening, DPI scaling, search, profile export, CLI integration.
- Total unit tests: 288 (was 267).

**Changelog (0.6.0):**
- `mcp_server.py` -- New. FastMCP server exposing 6 tools (wa_observe, wa_act, wa_task, wa_health, wa_list_windows, wa_manage_window) via stdio transport. Proxies to existing FastAPI backend on localhost:7862 via httpx. CLI: `windowsagent mcp`.
- `routes/agent.py` -- Added `GET /agent/stream` SSE endpoint using sse-starlette. EventSourceResponse with async generator, 30s keepalive pings.
- `_server_state.py` -- Added `agent_event_queue: asyncio.Queue | None` for SSE event bus.
- `agent_loop.py` -- Added `_emit_event(event_type, payload)` async function to push events to SSE queue.
- `server.py` -- Initialises `agent_event_queue` in startup_event().
- `voice/__init__.py` -- New package.
- `voice/stt.py` -- New. STT backend abstraction: `STTBackend` ABC, `OpenAICompatibleSTT` (Groq, OpenAI, self-hosted Speaches), `LocalWhisperSTT` (faster-whisper CPU). Factory: `create_stt_backend()`.
- `voice/pipeline.py` -- New. `VoicePipeline` class: `transcribe_file()` and `record_and_transcribe()` (sounddevice recording to WAV, delegates to STT backend).
- `replay.py` -- New. JSONL workflow replay: `load_workflow()`, `substitute_variables()` (${var} placeholders), `run_workflow()` (executes via Agent.act()). CLI: `windowsagent replay`.
- `config.py` -- Added 5 voice fields: stt_backend, stt_api_key, stt_base_url, stt_local_model, voice_hotkey.
- `cli.py` -- Added 3 commands: `mcp`, `voice`, `replay`.
- `pyproject.toml` -- Added `mcp` and `voice` optional dependency groups.
- Total unit tests: 267 (was 227). New test files: test_mcp_server.py (8), test_sse.py (6), test_voice_stt.py (13), test_voice_pipeline.py (5), test_replay.py (8).

**Changelog (0.5.1):**
- `apps/excel.py` — Verified against live Excel (Microsoft 365, Windows 11 UK English). Removed Formula Bar and sheet tabs (not exposed as named UIA elements). Corrected locale-dependent button names: "Font Colour", "Centre", "Merge & Centre", "AutoSum", "Sort & Filter". Added US English aliases for cross-locale support. Name Box confirmed as ComboBox aid="13".
- `apps/community/__init__.py` — New. Auto-discovery system using `pkgutil.iter_modules` + `inspect`. Scans `apps/community/` for `BaseAppProfile` subclasses, skips files starting with `_`, inserts discovered profiles before `GenericAppProfile`.
- `apps/community/_template.py` — New. Documented template with all `BaseAppProfile` fields and strategy methods.
- `apps/community/_template_meta.yml` — New. Metadata template (app name, author, tested versions, locales).
- `apps/community/CONTRIBUTING.md` — New. Contributor guide for submitting community profiles.
- `apps/__init__.py` — Integrated community profile auto-discovery. Community profiles load between built-in profiles and `GenericAppProfile`.
- `tests/test_input_actor.py` — New. 21 unit tests for input_actor.py (click, double-click, type, press_key, hotkey, scroll, move_to, DPI scaling).
- `tests/test_server.py` — New. 18 unit tests for all HTTP endpoints (health, observe, act, verify, windows, window/manage, spawn, shell).
- `tests/test_cli.py` — New. 19 unit tests for all CLI commands (version, config show, windows, window, observe, act).
- `tests/test_community_profiles.py` — New. 8 unit tests for auto-discovery, registration, and profile ordering.
- Total unit tests: 227 (was 161).

**Changelog (0.5.0):**
- `server.py` — Reduced from 746 to 98 lines. All endpoints extracted into route modules registered via `app.include_router()`.
- `routes/agent.py` — New. POST /observe, /act, /verify, /task + _serialise_element/_serialise_app_state helpers. Uses `_server_state` for shared agent/lock.
- `routes/system.py` — New. POST /spawn, /shell endpoints.
- `routes/browser.py` — Existing (v0.3.0). Now correctly wired into server.py via include_router (was dead code before this release).
- `routes/window.py` — Existing (v0.4.0). Now correctly wired into server.py via include_router (was dead code before this release).
- `agent.py` — Reduced from 464 to 266 lines. `run()` delegates to `agent_loop.run_task()`. Result dataclasses moved to `agent_types.py`. `_execute_type`/`_execute_scroll` wrappers removed (logic already in `agent_actions.py`).
- `agent_types.py` — New. ActionResult, VerifyResult, TaskResult dataclasses. Re-exported from `agent.py` for backwards compatibility.
- `agent_loop.py` — New. `run_task(agent, task, window_title, max_steps)` standalone function. Integrates RecoveryManager: focus recovery on failure, dialog detection/dismissal, circuit breaker.
- `recovery.py` — New. `RecoveryManager` class: circuit breaker (trips after N consecutive failures), `attempt_focus_recovery()` (re-activates window, retries step once), `detect_unexpected_dialog()` (scans window list for blocking dialogs), `dismiss_dialog()` (sends Escape).
- `exceptions.py` — Added `CircuitBreakerTrippedError` (not retryable), `UnexpectedDialogError` (retryable).
- `apps/excel.py` — New. ExcelProfile: 30 known_elements, 20 shortcuts, clipboard text strategy, scroll_pattern scroll, no focus restore.
- `cli.py` — Fixed `_serialise_app_state` import (now from `routes/agent.py`). Added `# type: ignore[operator]` for pywinctl Any-typed fn_map calls.
- `tests/test_recovery.py` — New. 16 unit tests for RecoveryManager.
- `tests/test_profile_dispatch.py` — 22 new tests for ExcelProfile.

**Changelog (0.4.0):**
- `window_manager.py` — New module. Cross-platform window lifecycle operations via pywinctl: activate, minimise, maximise, restore, move, resize, close, bring_to_front, send_to_back, get_geometry, is_alive/active/minimised/maximised/visible. Replaces scattered ctypes/win32gui calls with a single entry point. 28 unit tests.
- `actor/uia_actor.py` — Document typing now uses pywinctl `activate_by_hwnd()` for window activation, falling back to raw win32gui if pywinctl unavailable.
- `agent.py` — **Profile strategies now wired into the agent loop:**
  - `observe()` activates the target window via pywinctl before capturing state.
  - `_execute_action()` delegates scroll to `_execute_scroll()` — checks `profile.get_scroll_strategy()`: "webview2" routes to `webview2.scroll_content()`, "keyboard" sends Page Down/Up keys, "scroll_pattern" uses UIA ScrollPattern.
  - `_execute_action()` delegates type to `_execute_type()` — checks `profile.get_text_input_strategy()`: "clipboard" uses `clipboard.paste_to_element()`, "value_pattern" uses `uia_actor.type_text()`.
  - `act()` now calls `window_manager.activate()` after each action if `profile.requires_focus_restore()` returns True (Outlook, Teams, WebView2 apps).
  - New action types: activate, minimise/minimize, maximise/maximize, restore.
- `apps/outlook.py` — OutlookProfile now has 34 known_elements (New Mail, Reply, Forward, Delete, Search, Inbox, Calendar, compose fields, etc.) and 18 shortcuts (Ctrl+N, Ctrl+R, Ctrl+F, etc.). Overrides `get_text_input_strategy()` → "clipboard". Implements `on_before_act()` to escape reading pane focus trap before clicking.
- `server.py` — New `POST /window/manage` endpoint for window lifecycle operations.
- `cli.py` — New `windowsagent window` command for CLI window management.
- `__init__.py` — Exports `window_manager` module.
- `grounder/hybrid.py` — Removed unnecessary string annotation quote (UP037 fix).
- `tests/test_window_manager.py` — 28 unit tests + 2 integration tests.
- `tests/test_profile_dispatch.py` — 38 unit tests covering profile strategies, Outlook known_elements, shortcuts, and profile matching.
- `.claude/plans/current_mission.md` — Gap analysis: code vs spec, spec vs optimal goals.

**Changelog (0.3.0):**
- `browser/virtual_page.py` — VirtualElement + VirtualPage dataclasses. Structured page representation: role, name, bbox, interactivity flags, integer index. `to_llm_prompt()` produces compact text for LLM.
- `browser/grounder.py` — BrowserGrounding class. Connects via `playwright.chromium.connect_over_cdp()`. Two CDP calls per step: `Accessibility.getFullAXTree` + `DOMSnapshot.captureSnapshot`. Canvas elements flagged for screenshot fallback.
- `browser/launcher.py` — `launch_chrome_with_cdp()` spawns Chrome with `--remote-debugging-port`. `wait_for_cdp()` polls until CDP is ready.
- `server.py` — 5 new endpoints: `/browser/open`, `/browser/observe`, `/browser/act`, `/browser/screenshot`, `/browser/close`.
- `pyproject.toml` — Added `browser` optional dependency group (playwright, httpx).

**Changelog (0.2.0):**
- `actor/uia_actor.py` — Document typing now uses Win32 clipboard paste (SetClipboardData + Ctrl+V via keybd_event) instead of pywinauto `type_keys()`. Fixes 'f' character drop in WinUI3 apps caused by pywinauto's special key sequence parsing.
- `actor/clipboard.py` — `paste_to_element()` now uses Win32 `keybd_event` for Ctrl+A and Ctrl+V instead of pyautogui.hotkey, for consistency with the Document typing fix.
- `planner/task_planner.py` — `TaskPlanner.plan()` fully implemented. Uses Gemini Flash as primary LLM, Claude Haiku as fallback. Decomposes natural language tasks into `ActionStep` list. Includes `replan()` for error recovery.
- `planner/prompts.py` — Enhanced system prompt with detailed rules and `build_user_prompt()` helper.
- `agent.py` — `Agent.run()` fully implemented. Orchestrates Observe-Plan-Act-Verify loop with per-step logging and `max_steps` cap.
- `server.py` — `/task` endpoint fully implemented (was 501 stub). Accepts `{window, task, max_steps}`, returns `{success, steps_taken, steps, error}`.
- `recorder.py` — New module. Records `/act` and `/task` calls to JSONL files when `--record` flag is active. Foundation for Phase 3 replay.
- `cli.py` — Added `--record` flag to `windowsagent serve`.
- `start_server.bat` — Launcher script that sets `GEMINI_API_KEY` before starting server (for Scheduled Task use).

**Changelog (0.1.1):**
- `observer/uia.py` — `get_windows()` now uses `win32gui.EnumWindows` instead of pywinauto UIA `desktop.windows()`. Fixes a session isolation bug where `is_visible()` returned False for all windows when called from a background or service process context (WinUI3 apps, processes started by Scheduled Tasks in session 1).
- `actor/uia_actor.py` — `type_text()` for `Document` elements now uses `SetForegroundWindow` + pywinauto `type_keys()` via the top-level window HWND, falling back to pyautogui. Fixes typing into WinUI3 Notepad where all internal element HWNDs are 0.
- `agent.py` — `_execute_action()` passes `window_hwnd` (from `AppState`) to `type_text()` for Document elements.
- `server.py` — Added `/spawn` and `/shell` endpoints (see Section 8).

---

## 1. System Overview

WindowsAgent controls Windows desktop applications using a hybrid **UI Automation (UIA) + vision** approach. The primary strategy reads the OS accessibility tree — the same API used by screen readers — for precise, reliable element targeting. When accessibility data is insufficient (legacy apps, custom-rendered UIs, WebView2 content), the system falls back to a vision language model analysing a screenshot.

### Guiding Principles

1. **UIA-first, always.** The accessibility tree gives exact names, positions, and interaction patterns. Vision models hallucinate. Try UIA before touching a vision API.
2. **Verify every action.** Every `act()` call is followed by a `verify()` call. If the state didn't change, retry or escalate.
3. **App profiles encapsulate quirks.** Each app with known UIA oddities (WebView2, virtualised lists, custom controls) gets a dedicated profile in `apps/`.
4. **Fail loudly, not silently.** Raise typed exceptions. Never swallow errors. Log everything at appropriate levels.
5. **Config drives everything.** No hardcoded timeouts, model names, or retry counts. All configurable via `Config`.

---

## 2. Component Map (ASCII Diagram)

```
┌──────────────────────────────────────────────────────────────────┐
│                    User Input Layer                               │
│   CLI (cli.py)  │  HTTP API (server.py)  │  Python API (agent.py)│
└───────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│           Agent Loop (agent.py + agent_loop.py)                   │
│  Orchestrates: Observe → Ground → Act → Verify → loop/complete   │
│  agent_loop.py: run_task() + RecoveryManager integration          │
│  agent_types.py: ActionResult, VerifyResult, TaskResult           │
└──────┬──────────────┬───────────────┬────────────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────────────────────────────┐
│ Observer │   │ Grounder │   │              Actor               │
│          │   │          │   │                                  │
│ uia.py   │   │ uia_      │   │ uia_actor.py  (UIA patterns)    │
│ screen   │   │ grounder  │   │ input_actor.py (pyautogui)       │
│ shot.py  │   │ .py       │   │ clipboard.py  (Win32 clipboard)  │
│ ocr.py   │   │           │   └──────────────────────────────────┘
│ state.py │   │ vision_   │
└──────────┘   │ grounder  │   ┌──────────────────────────────────┐
               │ .py       │   │            Verifier              │
               │           │   │                                  │
               │ hybrid.py │   │ verify.py                        │
               └──────────┘   └──────────────────────────────────┘
                                         │
                    ┌────────────────────┘
                    ▼
       ┌──────────────────────────┐
       │       Apps Module        │
       │                          │
       │ base.py      (interface) │
       │ webview2.py  (WebView2)  │
       │ notepad.py               │
       │ file_explorer.py         │
       │ outlook.py               │
       │ excel.py     (Excel)     │
       │ generic.py               │
       └──────────────────────────┘
                    │
       ┌────────────┘
       ▼
┌──────────────────────────────────┐
│      Error Recovery              │
│      (recovery.py)               │
│                                  │
│   RecoveryManager:               │
│   circuit breaker, focus         │
│   recovery, dialog detection     │
└──────────────────────────────────┘
                    │
       ┌────────────┘
       ▼
┌──────────────────────────────────┐
│   Window Manager                 │
│   (window_manager.py)            │
│                                  │
│   pywinctl abstraction:          │
│   activate, minimise, maximise,  │
│   restore, move, resize, close,  │
│   is_alive, get_geometry,        │
│   find_window, get_all_windows   │
└──────────────────────────────────┘
                    │
       ┌────────────┘
       ▼
┌──────────────────────────┐
│      Config (config.py)  │
│  Loaded from: env vars   │
│  ~/.windowsagent/config  │
│  pyproject.toml section  │
└──────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 `observer/screenshot.py`

**Role:** Capture screenshots of the full desktop, a specific monitor, or a specific window.

**Primary backend:** `mss` (fastest, ~10ms per full capture)
**Fallback backend:** `pyautogui` (when mss fails)

**Key data type:**
```python
@dataclass
class Screenshot:
    image: PIL.Image.Image        # RGB PIL image
    dpi_scale: float              # e.g. 1.5 for 150% scaling
    timestamp: float              # time.time() at capture
    monitor_index: int            # 0 = all monitors combined, 1+ = specific monitor
    logical_width: int            # width in logical pixels
    logical_height: int           # height in logical pixels
    physical_width: int           # actual pixel width
    physical_height: int          # actual pixel height
```

**Public API:**
```python
def capture_full(config: Config) -> Screenshot
def capture_monitor(monitor_index: int, config: Config) -> Screenshot
def capture_window(hwnd: int, config: Config) -> Screenshot
def list_monitors() -> List[MonitorInfo]
def get_dpi_scale(hwnd: int = 0) -> float
```

**DPI strategy:** Call `ctypes.windll.shcore.GetScaleFactorForMonitor()` or `ctypes.windll.user32.GetDpiForWindow()`. Store both logical and physical dimensions. The agent always works in logical coordinates; screenshots are stored at physical resolution and the dpi_scale factor is used to translate when needed.

**Error behaviour:** Raises `ScreenshotError(message, retryable=True)` on failure.

---

### 3.2 `observer/uia.py`

**Role:** Inspect the Windows UI Automation accessibility tree. This is the most critical module — everything depends on it.

**Key data types:**
```python
@dataclass
class UIAElement:
    name: str                         # AccName (e.g. "Send", "File")
    control_type: str                 # "Button", "Edit", "List", "MenuItem", ...
    automation_id: str                # Developer-assigned ID (most stable)
    class_name: str                   # Win32 class name
    rect: tuple[int, int, int, int]   # (left, top, right, bottom) in logical px
    is_enabled: bool
    is_visible: bool                  # not offscreen, not covered
    patterns: list[str]               # ["InvokePattern", "ValuePattern", ...]
    value: str                        # current value/text (if ValuePattern)
    children: list['UIAElement']      # child elements (populated up to max_depth)
    depth: int                        # depth in tree (root = 0)
    hwnd: int                         # native window handle (0 if not applicable)

@dataclass
class UIATree:
    root: UIAElement
    window_title: str
    app_name: str                     # process name (e.g. "notepad.exe")
    timestamp: float
    pid: int
    hwnd: int

@dataclass
class WindowInfo:
    title: str
    app_name: str
    pid: int
    hwnd: int
    rect: tuple[int, int, int, int]
    is_visible: bool
    is_enabled: bool
```

**Public API:**
```python
def get_windows() -> list[WindowInfo]
def get_window(
    title: str | None = None,
    pid: int | None = None,
    hwnd: int | None = None,
) -> pywinauto.Application
def get_tree(window: pywinauto.Application, max_depth: int = 8) -> UIATree
def find_element(
    tree: UIATree,
    name: str | None = None,
    control_type: str | None = None,
    automation_id: str | None = None,
    value: str | None = None,
) -> UIAElement | None
def is_webview2(window: pywinauto.Application) -> bool
```

**Caching:** `get_tree()` results are cached for 500ms using a `(hwnd, max_depth)` key. Cache is invalidated if more than 500ms have elapsed or if the caller passes `force_refresh=True`.

**Error types raised:**
- `WindowNotFoundError(title, retryable=True)`
- `ElementNotFoundError(criteria, retryable=True)`
- `UIAError(message, retryable=False)` — base class

**find_element matching algorithm:**
1. Exact `automation_id` match (most stable)
2. Exact `name` + exact `control_type` match
3. Case-insensitive `name` + `control_type` match
4. Partial `name` match (name is contained in element.name)
5. `value` match (element.value contains the search value)
6. Returns the first match found via depth-first traversal
7. Returns `None` if no match (never raises)

---

### 3.3 `observer/ocr.py`

**Role:** Extract text and bounding boxes from screenshots when UIA tree is insufficient.

**Primary backend:** Windows OCR API via `winrt.windows.media.ocr` (no install required on Windows 10+)
**Fallback backend:** Tesseract (optional dependency via `[ocr]` extra)
**No-op mode:** When `config.ocr_backend == 'none'`, returns empty list

**Key data type:**
```python
@dataclass
class OCRResult:
    text: str
    bounding_box: tuple[int, int, int, int]  # (left, top, right, bottom) logical px
    confidence: float                         # 0.0-1.0 (Tesseract only; Windows OCR = 1.0)
    line_index: int                           # which OCR line this belongs to
```

**Public API:**
```python
def extract_text(screenshot: Screenshot, config: Config) -> list[OCRResult]
def find_text(
    screenshot: Screenshot,
    target: str,
    config: Config,
    case_sensitive: bool = False,
) -> list[OCRResult]
```

**Error behaviour:** Raises `OCRError(message, retryable=False)` on backend failure. Returns empty list (does not raise) if no text found.

---

### 3.4 `observer/state.py`

**Role:** Combine UIA tree, screenshot, and OCR into a single `AppState` snapshot. Compute diffs between states.

**Key data types:**
```python
@dataclass
class AppState:
    uia_tree: UIATree
    screenshot: Screenshot
    ocr_results: list[OCRResult]     # may be empty if OCR disabled
    focused_element: UIAElement | None
    window_title: str
    app_name: str
    pid: int
    hwnd: int
    timestamp: float
    is_webview2: bool

@dataclass
class StateDiff:
    new_elements: list[UIAElement]      # elements in after but not before
    removed_elements: list[UIAElement]  # elements in before but not after
    changed_elements: list[UIAElement]  # elements whose value/name changed
    screenshot_diff_pct: float          # 0.0-1.0 (fraction of pixels changed)
    has_new_window: bool                # new top-level window appeared
    has_dialog: bool                    # a dialog/modal appeared
```

**Public API:**
```python
def capture(window_title: str, config: Config) -> AppState
def diff(before: AppState, after: AppState) -> StateDiff
```

`capture()` calls `get_window()`, then `get_tree()`, `capture_window()`, and optionally `extract_text()` in parallel where possible. It catches individual failures and returns partial state (e.g. empty ocr_results if OCR fails).

---

### 3.5 `grounder/uia_grounder.py`

**Role:** Given a natural language description of a target element, find the best matching `UIAElement` in the tree.

**Algorithm:**
1. Parse description into search criteria: name keywords, control type hints, value hints
2. Run `find_element()` with extracted criteria
3. If no match, try progressively looser matching (see uia.py spec)
4. Return a `GroundedElement` with confidence score

**Public API:**
```python
def ground(
    description: str,
    tree: UIATree,
    context: str | None = None,
) -> GroundedElement | None
```

**Key data type:**
```python
@dataclass
class GroundedElement:
    method: Literal["uia", "vision", "ocr"]
    uia_element: UIAElement | None
    coordinates: tuple[int, int]        # centre point (logical px)
    confidence: float                   # 0.0-1.0
    bounding_rect: tuple[int, int, int, int]
    description_matched: str            # what description was used
```

---

### 3.6 `grounder/vision_grounder.py`

**Role:** Use a vision language model to identify an element's coordinates from a screenshot. Fallback when UIA tree fails.

**Supported models:** Gemini 2.5 Flash (default), Claude Haiku, Claude Sonnet
**Input:** Screenshot + text description of target element
**Output:** `GroundedElement` with `method="vision"`

**Request format (Gemini):**
- Send screenshot as base64 PNG
- Prompt: `"Find the UI element described as: '{description}'. Return the (x, y) centre coordinates of the element as JSON: {"x": int, "y": int}. If not found, return {"found": false}."`
- Parse JSON response; validate coordinates are within image bounds

**Public API:**
```python
def ground(
    description: str,
    screenshot: Screenshot,
    config: Config,
) -> GroundedElement | None
```

**Error behaviour:** Raises `VisionGrounderError(message, retryable=True)` on API failure. Returns `None` if element not found in the image.

---

### 3.7 `grounder/hybrid.py`

**Role:** Orchestrate UIA grounding with vision fallback. This is what the agent loop calls — it never calls the individual grounders directly.

**Algorithm:**
1. Try `uia_grounder.ground()` with `config.uia_timeout`
2. If result.confidence >= 0.7, return immediately
3. If UIA returns low confidence or `None`, try `vision_grounder.ground()` if a vision API key is configured
4. Return the best result (highest confidence), or `None` if both fail

**Public API:**
```python
def ground(
    description: str,
    state: AppState,
    config: Config,
) -> GroundedElement | None
```

**Logging:** Always log which method succeeded/failed and the confidence score.

---

### 3.8 `actor/uia_actor.py`

**Role:** Execute actions via Windows UI Automation patterns. This is the primary action execution path.

**UIA patterns used:**

| Action | Primary pattern | Fallback |
|--------|----------------|---------|
| click | InvokePattern | coordinate click |
| type_text | ValuePattern.SetValue | keyboard simulation |
| select | SelectionItemPattern | coordinate click |
| scroll | ScrollPattern | keyboard (Page Down/Up) |
| expand | ExpandCollapsePattern | coordinate click |
| toggle | TogglePattern | coordinate click |
| focus | Focus() | — |

**Public API:**
```python
def click(element: UIAElement, config: Config) -> bool
def type_text(element: UIAElement, text: str, config: Config) -> bool
def select(element: UIAElement, config: Config) -> bool
def scroll(element: UIAElement, direction: str, amount: int, config: Config) -> bool
def expand(element: UIAElement, config: Config) -> bool
def toggle(element: UIAElement, config: Config) -> bool
def focus(element: UIAElement, config: Config) -> bool
```

**Pre-conditions checked before each action:**
- `element.is_enabled` — raises `ElementDisabledError` if false
- `element.is_visible` — raises `ElementNotVisibleError` if false
- Element rect is non-zero

**Error types raised:**
- `ActionFailedError(action, element, reason, retryable=True)` — action failed after retries
- `ElementDisabledError(element)` — element exists but is disabled
- `ElementNotVisibleError(element)` — element is off-screen

---

### 3.9 `actor/input_actor.py`

**Role:** Fallback coordinate-based actions using pyautogui when UIA patterns fail or element has no UIA reference.

**DPI handling:** All input coordinates are in logical pixels. Before passing to pyautogui, multiply by `dpi_scale` to get physical coordinates.

**Public API:**
```python
def click_at(x: int, y: int, button: str = "left", config: Config = None) -> bool
def double_click_at(x: int, y: int, config: Config = None) -> bool
def right_click_at(x: int, y: int, config: Config = None) -> bool
def type_text(text: str, config: Config = None) -> bool
def press_key(key: str, config: Config = None) -> bool
def hotkey(*keys: str, config: Config = None) -> bool
def scroll_at(x: int, y: int, direction: str, amount: int, config: Config = None) -> bool
def move_to(x: int, y: int, config: Config = None) -> bool
```

**pyautogui safety:** `pyautogui.FAILSAFE = True` is always set. Mouse movements use `duration=0.1` to avoid instant jumps that confuse Windows focus management.

---

### 3.10 `actor/clipboard.py`

**Role:** Efficient data transfer for large text via the Win32 clipboard. Faster than simulating keypresses for long strings.

**Dependencies:** `win32clipboard` (pywin32)

**Public API:**
```python
def set_text(text: str) -> None
def get_text() -> str
def paste_to_element(element: UIAElement, text: str, config: Config) -> bool
def clear() -> None
```

`paste_to_element()`:
1. Focus the element
2. Call `set_text(text)`
3. Send `Ctrl+A` to select all existing content
4. Send `Ctrl+V` to paste
5. Returns True if element.value matches the pasted text

---

### 3.11 `verifier/verify.py`

**Role:** Confirm that an action produced the expected change. Drive retry logic in the agent loop.

**Public API:**
```python
def screenshot_diff(before: Screenshot, after: Screenshot) -> float
def uia_element_changed(before: UIAElement, after: UIAElement) -> bool
def action_succeeded(
    before: AppState,
    after: AppState,
    action: str,
    target: str,
) -> bool
def wait_for_change(
    hwnd: int,
    config: Config,
    timeout: float | None = None,
) -> bool
```

**`screenshot_diff` algorithm:**
1. Resize both images to the same dimensions if they differ
2. Convert to numpy arrays (if numpy available) or use PIL `ImageChops.difference()`
3. Sum absolute differences, divide by (width × height × 255 × 3)
4. Returns 0.0 for identical images, 1.0 for completely different

**`wait_for_change` algorithm:**
1. Capture baseline screenshot
2. Poll at 100ms intervals until `screenshot_diff(baseline, current) > 0.02` (2% change threshold)
3. Return True on first change detected
4. Return False if timeout elapsed without change

---

### 3.12 `apps/base.py`

**Role:** Abstract base class defining the interface every app profile must implement.

```python
from abc import ABC, abstractmethod

class BaseAppProfile(ABC):
    """Base class for all app-specific profiles."""

    app_names: list[str]        # process names this profile handles, e.g. ["notepad.exe"]
    window_titles: list[str]    # partial window title matches

    def __init__(self, config: Config) -> None: ...

    @abstractmethod
    def is_match(self, window_info: WindowInfo) -> bool:
        """Return True if this profile handles the given window."""
        ...

    def on_before_act(self, action: str, element: UIAElement | None) -> None:
        """Called before every action. Override to implement pre-action setup."""
        ...

    def on_after_act(self, action: str, element: UIAElement | None, success: bool) -> None:
        """Called after every action. Override to implement post-action cleanup."""
        ...

    def get_scroll_strategy(self) -> str:
        """Return preferred scroll strategy: 'scroll_pattern', 'keyboard', 'webview2'."""
        return "scroll_pattern"

    def requires_focus_restore(self) -> bool:
        """Return True if this app tends to steal focus (e.g. Outlook reading pane)."""
        return False
```

---

### 3.13 `apps/webview2.py`

**Role:** Special handling for Edge WebView2 applications. Shared by Outlook, Teams, VS Code.

**Detection:** A window contains WebView2 if it has child windows with class name `Chrome_WidgetWin_1` or `Chrome_RenderWidgetHostHWND`.

**Public API:**
```python
def is_webview2(window: pywinauto.Application) -> bool
def scroll_content(
    window: pywinauto.Application,
    direction: str,
    amount: int,
    config: Config,
) -> bool
def find_virtualised_item(
    window: pywinauto.Application,
    target_text: str,
    config: Config,
    max_scrolls: int = 20,
) -> UIAElement | None
def get_inner_tree(window: pywinauto.Application, config: Config) -> UIATree
```

**`scroll_content` algorithm:**
1. Find the content area (the WebView2 host element)
2. Click inside it to ensure keyboard focus
3. Send `Page Down` (or `Page Up`) key `amount` times
4. Wait 300ms for rendering
5. Capture screenshot diff to confirm scroll occurred
6. Return True if diff > 2%

**`find_virtualised_item` algorithm:**
1. Get currently visible UIA tree items
2. Search for `target_text` in visible items
3. If found, return the element
4. If not found, call `scroll_content()` (one page)
5. Refresh UIA tree
6. Repeat until found or `max_scrolls` exhausted
7. Return `None` if not found

---

### 3.14 `apps/notepad.py`

**Role:** Profile for Windows Notepad. Used as the primary test target.

**Public API:**
```python
def open(filepath: str | None = None, config: Config = None) -> pywinauto.Application
def type_text(app: pywinauto.Application, text: str, config: Config) -> bool
def save(app: pywinauto.Application, filepath: str | None = None, config: Config) -> bool
def select_all(app: pywinauto.Application, config: Config) -> bool
def get_text(app: pywinauto.Application, config: Config) -> str
def clear(app: pywinauto.Application, config: Config) -> bool
```

**`open` implementation:** `subprocess.Popen(['notepad.exe', filepath])` if filepath provided, else `subprocess.Popen(['notepad.exe'])`. Wait for window with `pywinauto.timings.wait_until_passes()`.

**`get_text` implementation:** Locate the Edit control in the UIA tree, use `ValuePattern.Value` or `LegacyIAccessiblePattern.Value`. Fall back to `Ctrl+A`, `Ctrl+C`, read clipboard.

---

### 3.15 `apps/file_explorer.py`

**Role:** Profile for Windows File Explorer (explorer.exe).

**Public API:**
```python
def open(path: str | None = None, config: Config = None) -> pywinauto.Application
def navigate(app: pywinauto.Application, path: str, config: Config) -> bool
def list_items(app: pywinauto.Application, config: Config) -> list[str]
def click_item(app: pywinauto.Application, name: str, config: Config) -> bool
def double_click_item(app: pywinauto.Application, name: str, config: Config) -> bool
def create_folder(app: pywinauto.Application, name: str, config: Config) -> bool
def delete_item(app: pywinauto.Application, name: str, config: Config) -> bool
def rename_item(app: pywinauto.Application, old_name: str, new_name: str, config: Config) -> bool
```

**`navigate` implementation:** Find the address bar (automation_id: "Address Band Root"), click it, select all, type path, press Enter. This is faster than clicking through folders.

**`create_folder` implementation:** Right-click in content area → "New" → "Folder" → type name → Enter. Uses UIA context menu navigation.

**`delete_item` implementation:** Click item to select, press `Delete` key. Note: moves to Recycle Bin, does NOT permanently delete.

---

### 3.16 `apps/outlook.py`

**Role:** Profile for Microsoft Outlook (new Outlook, WebView2-based).

**Key quirks:**
- Email list is virtualised (only ~15 emails in UIA tree at once)
- Reading pane steals focus when an email is clicked
- New Outlook runs as `olk.exe` or inside `msedgewebview2.exe`

**Inherits from:** `BaseAppProfile` (calls `super()` for standard operations, overrides scroll and focus methods)

**Public API:**
```python
def open(config: Config = None) -> pywinauto.Application
def scroll_email_list(app: pywinauto.Application, direction: str, config: Config) -> bool
def find_email(app: pywinauto.Application, subject: str, config: Config) -> UIAElement | None
def click_email(app: pywinauto.Application, subject: str, config: Config) -> bool
def get_reading_pane_text(app: pywinauto.Application, config: Config) -> str
```

**`requires_focus_restore` returns:** `True`

---

### 3.17 `apps/generic.py`

**Role:** Fallback profile used when no specific app profile matches.

Implements all `BaseAppProfile` methods with sensible defaults. Uses standard UIA scroll patterns, does not override focus behaviour. Any app without a dedicated profile uses this.

---

### 3.18 `planner/task_planner.py`

**Role:** LLM-based task decomposition. Decomposes natural language tasks into `ActionStep` sequences.

**LLM selection:**
1. Gemini Flash (primary) — if `GEMINI_API_KEY` is set and `vision_model` starts with "gemini"
2. Claude Haiku (fallback) — if `ANTHROPIC_API_KEY` is set

**Flow:** Summarise AppState → build prompt → call LLM → parse JSON → return `list[ActionStep]`

```python
class TaskPlanner:
    def plan(self, task: str, state: AppState) -> list[ActionStep]: ...
    def replan(self, task: str, state: AppState, completed_steps: list[ActionStep], error: str) -> list[ActionStep]: ...
```

### 3.18b `recorder.py`

**Role:** Records `/act` and `/task` calls to JSONL files when `config.record_replays` is True or `--record` CLI flag is active.

**Format:** One JSON object per line:
```json
{"timestamp": 1710000000.0, "window": "Notepad", "action": "type", "element": "Text Editor", "params": {"text": "Hello"}, "result": {"success": true}}
```

---

### 3.19 `agent.py`

**Role:** Main orchestration loop. Ties all modules together.

**Class:**
```python
class Agent:
    def __init__(self, config: Config | None = None) -> None: ...

    def observe(self, window_title: str) -> AppState: ...

    def act(
        self,
        window_title: str,
        action: str,
        target: str,
        params: dict | None = None,
    ) -> ActionResult: ...

    def verify(self, window_title: str, expected_change: str) -> VerifyResult: ...

    def run(self, task: str, window_title: str) -> TaskResult:
        """Full Observe-Plan-Act-Verify loop. Phase 1: raises NotImplementedError
        (task planner not yet implemented). Use act() directly in Phase 1."""
        raise NotImplementedError("Full task execution requires task planner (Phase 2).")
```

**`act()` implementation:**
1. `capture()` state before
2. `hybrid.ground()` to find element
3. Select app profile (or generic)
4. `profile.on_before_act()`
5. `uia_actor` or `input_actor` executes action
6. `profile.on_after_act()`
7. Returns `ActionResult(success, error, grounded_element, state_before)`

---

### 3.20 `server.py`

**Role:** FastAPI HTTP server exposing the agent API on localhost:7862.

**Endpoints:**

| Method | Path | Request body | Response | Notes |
|--------|------|-------------|----------|-------|
| GET | /health | — | `{status, version, uptime}` | Always returns 200 |
| GET | /windows | — | `List[WindowInfo]` | All visible top-level windows |
| POST | /observe | `{window: str}` | `AppState` as JSON | Captures current state |
| POST | /act | `{window, action, element, params}` | `{success, error, diff_pct}` | Execute single action |
| POST | /verify | `{window, expected_change}` | `{success, diff_pct}` | Check action succeeded |
| POST | /spawn | `{executable, args, cwd}` | `{success, pid, cmd}` | Launch visible process in user session with `CREATE_NEW_CONSOLE` |
| POST | /shell | `{command, shell, cwd, timeout}` | `{success, stdout, stderr, returncode, duration_ms}` | Run shell command in user session, capture output |
| POST | /task | `{window, task, max_steps?}` | `{success, steps_taken, steps, error}` | LLM-planned task execution |

**Security:** Binds to `127.0.0.1` only (never `0.0.0.0`). No authentication for localhost-only use. If `config.server_host` is changed from `127.0.0.1`, warn loudly in logs.

#### Session Isolation Note

On Windows, processes spawned by services (including most AI orchestration systems like OpenClaw) run as `SYSTEM` or another service account in **Session 0** — the non-interactive desktop. Session 0 is fully isolated from the user's interactive session (Session 1+). This means:

- `win32gui.EnumWindows` returns 0 results from Session 0
- `pyautogui.click()` targets the wrong desktop
- User environment variables and `PATH` are absent

**Solution:** Run `windowsagent serve` via a Windows Scheduled Task configured with `LogonType = Interactive` and the target user account. The Scheduled Task starts the server in the user's interactive session. The HTTP API is then callable from any session (including Session 0 orchestrators) — the requests are just network calls, not desktop operations.

The `/spawn` endpoint creates child processes inside the server's (user) session using `CREATE_NEW_CONSOLE`, giving them visible windows.
The `/shell` endpoint runs subprocesses with captured stdout/stderr in the user's session, giving AI agents access to the correct user environment.

---

### 3.21 `cli.py`

**Role:** Click-based command-line interface.

**Commands:**
```
windowsagent windows          List all visible windows
windowsagent observe          Capture UIA tree + screenshot
  --window TEXT               Window title (required)
  --depth INT                 Max UIA tree depth (default: 8)
  --output-dir PATH           Save screenshot here
windowsagent act              Execute a single action
  --window TEXT               Window title (required)
  --action TEXT               Action type: click|type|scroll|key|expand
  --element TEXT              Target element description
  --text TEXT                 Text for type action
  --key TEXT                  Key for key action
  --direction TEXT            Scroll direction: up|down|left|right
  --amount INT                Scroll amount
windowsagent serve            Start HTTP API server
  --host TEXT                 Bind host (default: 127.0.0.1)
  --port INT                  Bind port (default: 7862)
  --record                    Record actions to JSONL
windowsagent window           Manage window state
  --title TEXT                Window title (required)
  --action TEXT               activate|minimise|maximise|restore|close|geometry|bring-to-front|send-to-back
windowsagent version          Show version
windowsagent config show      Show current config
```

### 3.22 `window_manager.py`

**Role:** Cross-platform window lifecycle operations via pywinctl. Single entry point for all window management, replacing scattered ctypes and win32gui calls.

**Why pywinctl over raw win32gui:**
- Cross-platform potential (macOS/Linux support for future portability)
- Higher-level API (one call vs SetForegroundWindow + ShowWindow + SW_RESTORE)
- Built-in `wait` parameter for state transitions
- Window alive checks and z-order control

**Key types:**
- `WindowGeometry` — dataclass with left, top, width, height, computed right/bottom/centre

**Functions:**
```
# Finding windows
get_active_window() → Window | None
get_all_windows() → list[Window]
get_all_titles() → list[str]
find_windows(title) → list[Window]     # substring, case-insensitive
find_window(title) → Window            # raises WindowNotFoundError
get_window_by_hwnd(hwnd) → Window | None

# Window state management
activate(window, wait=True) → bool     # restore if minimised, then activate
activate_by_hwnd(hwnd, wait=True) → bool
minimise(window, wait=True) → bool
maximise(window, wait=True) → bool
restore(window, wait=True) → bool
close(window) → bool

# Positioning
move(window, x, y) → bool
resize(window, width, height) → bool
get_geometry(window) → WindowGeometry

# State queries
is_alive(window) → bool
is_active(window) → bool
is_minimised(window) → bool
is_maximised(window) → bool
is_visible(window) → bool

# Z-order
bring_to_front(window) → bool
send_to_back(window) → bool

# Monitor info
get_display_info(window) → dict
get_all_screens() → dict
```

**Integration points:**
- `agent.py` — `observe()` calls `activate()` before capturing state
- `agent.py` — `_execute_action()` supports activate/minimise/maximise/restore actions
- `actor/uia_actor.py` — Document typing uses `activate_by_hwnd()` for foreground
- `server.py` — `POST /window/manage` endpoint exposes all operations via HTTP
- `cli.py` — `windowsagent window` command for CLI window management

**All functions accept either a pywinctl Window object or a title string** (auto-resolved via `find_window()`).

---

## 4. Data Flow Diagrams

### 4.1 Happy Path — Single Action

```
User: windowsagent act --window "Notepad" --action type --element "Text Editor" --text "Hello"
  │
  ▼
cli.py: parse args → Agent.act(window="Notepad", action="type", target="Text Editor", params={"text":"Hello"})
  │
  ▼
agent.py: state_before = capture("Notepad")
  │         uia_tree captured, screenshot taken
  ▼
hybrid.py: ground("Text Editor", state_before, config)
  │         → uia_grounder finds Edit control named "Text Editor", confidence=0.95
  │         → returns GroundedElement(method="uia", uia_element=..., confidence=0.95)
  ▼
apps/notepad.py: on_before_act("type", element) → sets focus
  │
  ▼
uia_actor.py: type_text(element, "Hello", config)
  │             → element has ValuePattern → ValuePattern.SetValue("Hello")
  │             → returns True
  ▼
verify.py: wait_for_change(hwnd, config, timeout=3.0)
  │         → screenshot diff > 2% after 150ms → returns True
  ▼
agent.py: returns ActionResult(success=True, diff_pct=0.15)
  │
  ▼
cli.py: prints "✓ Action succeeded (15% change detected)"
```

### 4.2 UIA Grounding Failure → Vision Fallback

```
hybrid.py: ground("blue submit button", state, config)
  │
  ├─ uia_grounder.ground("blue submit button", tree, context)
  │    → no element matches ("blue" is not an accessibility property)
  │    → returns None
  │
  ├─ [confidence < 0.7, try vision]
  │
  ├─ vision_grounder.ground("blue submit button", screenshot, config)
  │    → sends screenshot to Gemini Flash API
  │    → Gemini returns {"x": 450, "y": 320}
  │    → returns GroundedElement(method="vision", coordinates=(450,320), confidence=0.85)
  │
  └─ returns GroundedElement(method="vision", ...)

WARNING logged: "UIA grounding failed for 'blue submit button', fell back to vision (confidence=0.85)"
```

### 4.3 WebView2 Scroll Sequence (Outlook Email List)

```
apps/outlook.py: scroll_email_list(app, direction="down", config)
  │
  ├─ webview2.is_webview2(app) → True
  │
  ├─ webview2.scroll_content(app, direction="down", amount=1, config)
  │    │
  │    ├─ screenshot_before = capture_window(hwnd, config)
  │    │
  │    ├─ find content area: search for Chrome_RenderWidgetHostHWND child
  │    │
  │    ├─ input_actor.click_at(content_area.centre_x, content_area.centre_y)
  │    │    → establishes keyboard focus in WebView2 content
  │    │
  │    ├─ input_actor.press_key("page_down")
  │    │    → WebView2 receives key event, scrolls list
  │    │
  │    ├─ time.sleep(0.3)  # wait for rendering
  │    │
  │    ├─ screenshot_after = capture_window(hwnd, config)
  │    │
  │    ├─ diff = screenshot_diff(screenshot_before, screenshot_after)
  │    │    → diff = 0.35 (35% of pixels changed — new emails loaded)
  │    │
  │    └─ returns True (diff > 0.02 threshold)
  │
  └─ UIA tree re-inspected: 15 new email items now visible
```

### 4.4 Record-and-Replay Capture Format (Phase 2 placeholder)

```json
{
  "schema_version": "1.0",
  "captured_at": "2026-03-03T10:00:00Z",
  "app_name": "notepad.exe",
  "window_title": "Untitled - Notepad",
  "steps": [
    {
      "step_index": 0,
      "action": "type",
      "target": "Text Editor",
      "grounding_method": "uia",
      "automation_id": "15",
      "control_type": "Edit",
      "params": {"text": "Hello World"},
      "screenshot_before_b64": "...",
      "screenshot_after_b64": "...",
      "diff_pct": 0.12,
      "duration_ms": 145
    }
  ],
  "variables": {
    "text_to_type": "Hello World"
  }
}
```

Phase 2 will implement recording capture (hook into `Agent.act()`) and replay execution (parse JSON, execute each step, substitute variables). This format is **not implemented in Phase 1** but the schema is defined here for planning.

---

## 5. Error Handling Contracts

### Exception Hierarchy

```
WindowsAgentError (base, all exceptions inherit from this)
├── ObserverError
│   ├── ScreenshotError(message, retryable: bool)
│   ├── UIAError(message, retryable: bool)
│   │   ├── WindowNotFoundError(title: str)
│   │   └── ElementNotFoundError(criteria: dict)
│   └── OCRError(message)
├── GrounderError
│   ├── GroundingFailedError(description: str, methods_tried: list[str])
│   └── VisionGrounderError(message, retryable: bool)
├── ActorError
│   ├── ActionFailedError(action: str, element: UIAElement | None, reason: str, retryable: bool)
│   ├── ElementDisabledError(element: UIAElement)
│   └── ElementNotVisibleError(element: UIAElement)
└── VerifierError
    └── VerificationTimeoutError(timeout: float)
```

All exceptions include:
- `message: str` — human-readable description
- `retryable: bool` — whether the agent loop should retry
- `context: dict` — arbitrary diagnostic context (window title, element name, etc.)

### Agent Loop Error Handling

The agent loop in `agent.py` handles errors as follows:

| Exception | Action |
|-----------|--------|
| `WindowNotFoundError` | Re-attempt after 1s (window may be loading), max 3 retries |
| `ElementNotFoundError` | Re-capture state, try again. After 2 failures, try vision fallback |
| `ActionFailedError(retryable=True)` | Wait `config.retry_delay`, retry up to `config.max_retries` |
| `ActionFailedError(retryable=False)` | Report failure immediately, do not retry |
| `ElementDisabledError` | Wait 500ms (element may become enabled), retry once |
| `GroundingFailedError` | Report failure with screenshot. Cannot proceed without a target. |
| Any unhandled exception | Log at ERROR level, return failure result. Never crash the server. |

---

## 6. State Management

The agent maintains an `AgentState` object for the duration of a task:

```python
@dataclass
class AgentState:
    task: str                              # original user request
    plan: list[ActionStep]                 # from task planner (empty in Phase 1)
    current_step_index: int                # current position in plan
    step_history: list[StepRecord]         # history of completed steps
    retry_count: int                       # retries for current step
    total_actions: int                     # global counter (hard limit: 200)
    start_time: float                      # task start timestamp
    window_handle: int                     # target window HWND
    last_state: AppState | None            # most recent captured state
    status: Literal["running", "completed", "failed", "awaiting_confirmation"]
```

State is **ephemeral** — held in memory only for the duration of one `Agent.run()` call or one HTTP request session. There is no cross-task persistence in Phase 1.

**Safety limits:**
- `total_actions` hard limit: 200 actions per task (prevents infinite loops)
- Per-step retry limit: `config.max_retries` (default: 3)
- Task timeout: `config.task_timeout` (default: 300 seconds / 5 minutes)

---

## 7. Threading Model

| Component | Thread model | Notes |
|-----------|-------------|-------|
| `observer/screenshot.py` | Synchronous | mss is thread-safe but capture is fast enough to be sync |
| `observer/uia.py` | Synchronous | pywinauto UIA calls are synchronous; caching is thread-local |
| `observer/ocr.py` | Synchronous | Windows OCR API is sync |
| `observer/state.py` | Runs screenshot + UIA concurrently via `concurrent.futures.ThreadPoolExecutor` | OCR runs after screenshot; UIA runs in parallel |
| `actor/uia_actor.py` | Synchronous | UIA pattern calls are blocking |
| `actor/input_actor.py` | Synchronous | pyautogui is not thread-safe; must run in main thread or with locks |
| `verifier/verify.py` | Synchronous | Polling loop in `wait_for_change` |
| `server.py` | Async (FastAPI + uvicorn) | Each request handled in async context; blocking calls run in `asyncio.run_in_executor()` |
| `agent.py` | Synchronous internally | Agent loop is blocking; server wraps in executor |

**Key rule:** `pyautogui` must never be called from multiple threads simultaneously. The server uses a per-agent lock (`asyncio.Lock`) to serialise requests.

---

## 8. Config System

Full schema for `config.py`:

```python
@dataclass
class Config:
    # Vision model
    vision_model: str = "gemini-flash"       # gemini-flash | claude-haiku | claude-sonnet | none
    vision_api_key: str = ""                  # auto-loaded from GEMINI_API_KEY or ANTHROPIC_API_KEY

    # Screenshot backend
    screenshot_backend: str = "mss"           # mss | pyautogui

    # OCR backend
    ocr_backend: str = "windows"              # windows | tesseract | none

    # Timeouts (seconds)
    uia_timeout: float = 5.0
    vision_timeout: float = 15.0
    verify_timeout: float = 3.0
    task_timeout: float = 300.0

    # Retry
    max_retries: int = 3
    retry_delay: float = 0.5

    # Safety
    confirm_sensitive: bool = True            # require confirmation for delete/send/submit
    max_actions_per_task: int = 200

    # Record/replay (Phase 2)
    record_replays: bool = False
    replay_dir: str = "./replays"

    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 7862

    # Logging
    log_level: str = "INFO"                   # DEBUG | INFO | WARNING | ERROR

    # UIA cache
    uia_cache_ttl: float = 0.5               # seconds to cache UIA tree
```

**Loading order (later overrides earlier):**
1. Dataclass defaults
2. `~/.windowsagent/config.json` (if exists)
3. `pyproject.toml [tool.windowsagent]` section (if exists in cwd)
4. Environment variables (e.g. `WINDOWSAGENT_UIA_TIMEOUT=10.0`)

**Environment variable naming:** `WINDOWSAGENT_` prefix + field name uppercased. E.g. `WINDOWSAGENT_VISION_MODEL=claude-haiku`.

---

## 9. Testing Strategy

### Unit Tests (no Windows apps required)

| Test file | What it tests |
|-----------|---------------|
| `tests/test_observer.py` | Screenshot capture, DPI detection, UIA tree parsing, find_element algorithm |
| `tests/test_grounder.py` | UIA grounding with mock trees, hybrid fallback logic |
| `tests/test_actor.py` | Action execution with mock elements, clipboard roundtrip |
| `tests/test_verifier.py` | Screenshot diff algorithm, same-image = 0.0, diff-image > 0.0 |
| `tests/test_config.py` | Config loading from env vars, JSON file, defaults |

### Integration Tests (require real Windows)

| Test file | App | Task |
|-----------|-----|------|
| `tests/apps/test_notepad.py` | Notepad | Open → type "Hello World" → verify text in edit control |
| `tests/apps/test_file_explorer.py` | File Explorer | Navigate to C:\ → list items → verify "Windows" folder present |

### Running Tests

```bash
# Unit tests (no Windows apps needed)
pytest tests/ -k "not test_notepad and not test_file_explorer" -v

# Integration tests (Windows apps needed, run on Windows 10/11 only)
pytest tests/apps/ -v

# All tests with coverage
pytest tests/ --cov=windowsagent --cov-report=html
```

### CI/CD Matrix

```yaml
# GitHub Actions: .github/workflows/test.yml (not created in Phase 1)
os: [windows-latest]
python-version: ['3.10', '3.11', '3.12']
```

---

## 10. Security Considerations

### Action Classification

**Tier 1 — Safe (no confirmation):**
- `observe()`, `get_windows()`, screenshot capture
- `scroll`, `click` on non-destructive elements
- `type_text` in text editors

**Tier 2 — Sensitive (confirmation required when `config.confirm_sensitive = True`):**
- Clicking "Send", "Delete", "Submit", "Confirm", "OK" on destructive dialogs
- Any action where target element name contains: "delete", "remove", "send", "submit", "purchase", "buy", "pay"

**Tier 3 — Blocked:**
- Interacting with UAC prompt windows (class name `Credential Dialog Xaml Host`)
- Actions that would interact with password fields (control_type = "PasswordField")
- Running shell commands (no exec/subprocess in actor modules)

### Prompt Injection Defence

The vision grounder sends element descriptions to external LLM APIs. If a malicious element on screen contains text like "Ignore all previous instructions", this could be in the screenshot sent to the vision API.

Mitigation in Phase 1: Vision calls send only the target description (natural language), not raw screen text. The screenshot is sent as an image, not transcribed text, which limits injection vectors.

Phase 2 will add: sandboxed prompts with explicit output format enforcement (JSON only), content filters on vision responses.

### HTTP API Security

- Server binds to `127.0.0.1` only
- No CORS headers added (browser JS cannot call it)
- No authentication (local-only by design)
- If `config.server_host != "127.0.0.1"`, startup logs a `WARNING: Server exposed beyond localhost`

---

## 11. Performance Targets

| Operation | Target latency | Notes |
|-----------|---------------|-------|
| Screenshot (full desktop) | < 50ms | mss is ~10ms; 50ms budget includes PIL conversion |
| UIA tree capture (Notepad) | < 200ms | Simple app with shallow tree |
| UIA tree capture (Outlook) | < 1000ms | Deep tree, WebView2 content |
| UIA grounding (exact match) | < 100ms | Tree already captured |
| Vision grounding (Gemini Flash) | < 3000ms | Network + model latency |
| Action execution (click) | < 200ms | InvokePattern is fast |
| Action execution (type 100 chars) | < 500ms | ValuePattern.SetValue is fast; keyboard sim is ~50ms/char |
| Verify (screenshot diff) | < 200ms | PIL diff on 1080p image |
| Full act() cycle (UIA path) | < 1000ms | Observe + Ground + Act + Verify |
| Full act() cycle (vision path) | < 5000ms | Includes Gemini API call |

---

## 12. Phase 1 Done Criteria

Phase 1 is complete when all of the following pass:

- [ ] `pip install windowsagent` succeeds (after PyPI publish)
- [ ] `windowsagent windows` lists all visible windows
- [ ] `windowsagent observe --window "Notepad"` returns UIA tree + saves screenshot
- [ ] `windowsagent act --window "Notepad" --action type --element "Text Editor" --text "Hello"` types text in Notepad
- [ ] `windowsagent serve` starts HTTP server on port 7862
- [ ] GET /health returns `{"status": "ok"}`
- [ ] POST /observe with `{"window": "Notepad"}` returns AppState JSON
- [ ] POST /act executes a type action in Notepad
- [ ] All unit tests pass (`pytest tests/ -k "not test_notepad and not test_file_explorer"`)
- [ ] Integration test `test_notepad.py` passes (types "Hello World" in Notepad)
- [ ] Integration test `test_file_explorer.py` passes (navigates to C:\)
- [ ] `ruff check windowsagent/` returns 0 errors
- [ ] `mypy windowsagent/` returns 0 errors (strict mode)

---

## 13. Skills Distribution

The `skills/` directory ships ready-to-use AI skills that wrap the WindowsAgent HTTP API for multiple platforms:

```
skills/
  openclaw/           — 11 SKILL.md files for OpenClaw AI assistant
  mcp/bridge.py       — Python MCP stdio server wrapping all 6 HTTP endpoints
  mcp/windowsagent.json — Config snippet for Claude Desktop / Cursor MCP
  cursor/windowsagent.mdc — Cursor rules file with endpoint reference
  README.md           — Platform setup guide
```

### OpenClaw Skills

Each skill is a self-contained Markdown file with:
- Verified UIA element names (sourced from `windowsagent/apps/` profiles)
- PowerShell helper functions using `ConvertTo-Json` + `curl.exe`
- Keyboard shortcut references
- Fallback strategies when UIA fails

Skills are sanitised for public distribution — no personal data, paths use `%USERPROFILE%`, examples use generic values.

### MCP Bridge

`bridge.py` is a Python MCP stdio server (requires `mcp` and `httpx` packages) that exposes 6 tools:
- `wa_observe` — GET /observe
- `wa_act` — POST /act
- `wa_task` — POST /task
- `wa_shell` — POST /shell
- `wa_spawn` — POST /spawn
- `wa_health` — GET /health

Base URL is configurable via `WA_BASE_URL` environment variable (default: `http://localhost:7862`).

### Cursor Rules

`windowsagent.mdc` provides Cursor with full context about WindowsAgent endpoints, app element names, and common patterns so it can generate correct API calls without trial and error.

---

## 14. Browser Grounding (CDP)

WindowsAgent's UIA pipeline controls desktop apps. For **browser content**, the UIA tree sees Chrome as a single opaque window. The browser grounding module connects directly to Chrome's DevTools Protocol (CDP) for native access to the browser's own accessibility tree and DOM layout.

### Architecture

```
Chrome (--remote-debugging-port=9222)
    │
    ├── CDP WebSocket
    │     ├── Accessibility.getFullAXTree    → roles, names, states
    │     └── DOMSnapshot.captureSnapshot    → bounding boxes (includeDOMRects=true)
    │
    └── Joined by backendDOMNodeId
          │
          └── VirtualPage (flat element list with integer indices)
                │
                ├── to_llm_prompt()   → compact text for LLM: [1] button "Sign In" (450,120)
                ├── find_by_index()   → look up element by LLM index
                └── find_by_role_name() → search by ARIA role + name
```

### Performance

Based on browser-use/Stagehand v3 research (2025):
- DOM-based agents: **68s/task avg** vs screenshot-based: **225s/task avg** (3.3x slower)
- Each screenshot adds ~0.8s LLM encoding overhead
- Two CDP calls per step: **~50-200ms total**

### Components

| File | Purpose |
|------|---------|
| `browser/__init__.py` | Package exports: VirtualElement, VirtualPage, BrowserGrounding |
| `browser/virtual_page.py` | VirtualElement + VirtualPage dataclasses |
| `browser/grounder.py` | BrowserGrounding class — CDP connection, capture, act |
| `browser/launcher.py` | launch_chrome_with_cdp(), wait_for_cdp() |

### Key Design Decisions

1. **Playwright connect_over_cdp()** for v1 — clean Python async API, no raw WebSocket management. Raw CDP migration is a future optimisation.
2. **SPA freshness** — re-extract VirtualPage at the start of every step. Never cache across steps (backendDOMNodeId invalidated by navigation and React remounts).
3. **Canvas fallback** — elements with `role="img"` and `tag="canvas"` get `needs_vision_fallback=True`. Use `screenshot_element()` for these.
4. **Integer indexing** — interactable elements get sequential indices (0, 1, 2...), non-interactable get -1. LLM references elements by index.
5. **Cross-origin iframes** — skipped in v1. Needs `Target.attachToTarget` (v2).

### Interactable Roles

```python
INTERACTABLE_ROLES = {
    "button", "link", "textbox", "combobox", "listbox", "option",
    "checkbox", "radio", "menuitem", "tab", "searchbox", "spinbutton",
    "slider", "switch", "treeitem", "columnheader", "rowheader",
}
```

### HTTP API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/browser/open` | POST | Launch Chrome with CDP, connect grounder |
| `/browser/observe` | POST | Capture VirtualPage (elements + page text) |
| `/browser/act` | POST | click, type, scroll, key, navigate by element index |
| `/browser/screenshot` | GET | Viewport or element screenshot (base64 PNG) |
| `/browser/close` | POST | Disconnect CDP, optionally kill Chrome |

### Known Limitations

1. Canvas/WebGL content → screenshot fallback only
2. Closed shadow DOM → inaccessible with any external tool
3. `Accessibility.getFullAXTree` is "Experimental" in CDP spec — stable in practice since 2017
4. AX tree inaccurate on poorly-authored sites (no ARIA labels) → fallback to JS heuristics (future)
5. Cross-origin iframes → v2 via Target.attachToTarget

---

## 15. UIA Element Overlay

**Role:** Visual debugging tool that draws colour-coded bounding boxes over UI Automation elements. Helps developers inspect element properties and build community app profiles.

**Architecture:** Runs as a standalone PyQt6 window process. Fetches UIA data via HTTP API (`localhost:7862/observe`) — no direct UIA calls. Three modules: `renderer.py` (pure functions + OverlayWindow), `widget.py` (PyQt6 QWidget), `inspector.py` (search + profile export).

**Key features:**
- Transparent frameless always-on-top window (`FramelessWindowHint | WindowStaysOnTopHint | Tool`)
- Colour-coded by control type: Button=blue, Edit=green, List=orange, Menu=red, Tab=purple, etc.
- Click-to-inspect: selects smallest element under cursor, highlights in yellow
- Search: type to filter elements by name/automation_id/control_type
- Profile export: `generate_profile_snippet()` creates BaseAppProfile subclass code
- DPI-aware: auto-detects scale via `get_dpi_scale()`, scales all coordinates

**Public API:**
```python
from windowsagent.overlay import OverlayWindow, search_elements, generate_profile_snippet

# Launch overlay
overlay = OverlayWindow(target_window="Notepad", refresh_ms=2000)
overlay.start()  # Blocks until Escape pressed

# Search and export (used by inspector UI)
matches = search_elements(elements, "save")
snippet = generate_profile_snippet("myapp.exe", entries)
```

**CLI:** `windowsagent overlay --window "Notepad" [--refresh 2000]`

**Dependencies:** PyQt6 >=6.5 (optional `[overlay]` extra), httpx

**Files:**
- `overlay/__init__.py` — package exports
- `overlay/renderer.py` — colour mapping, flatten_elements, scale_rect, fetch_*, OverlayWindow (184 lines)
- `overlay/widget.py` — _OverlayWidget QWidget subclass (127 lines)
- `overlay/inspector.py` — search_elements, element_to_profile_entry, generate_profile_snippet (98 lines)
- `tests/test_overlay.py` — 21 unit tests

---

## 16. Known Technical Debt (as of 0.6.0)

| Issue | Severity | Impact |
|-------|----------|--------|
| 2 pre-existing RUF005 in routes/system.py (/spawn, /shell) | Low | Use unpacking syntax instead of concatenation |
| `routes/window.py` catches HTTPException(400) in broad `except Exception` and re-wraps as 500 | Low | Unknown actions return 500 instead of 400 |
| `agent.py` is 266 lines (limit: 250) | Low | 16 lines over — act() method is inherently complex |
| No replay video generation | Medium | S-grade feature: --record to .mp4 + .gif |
| No plugin system | High | Phase 3: 5 hooks (on_observe, on_plan, on_act, on_verify, on_complete) |
| DPI scaling untested at 125%/150% | Medium | Only 100% verified |
| vision_grounder.py, ocr.py, recorder.py still untested | Medium | Lower priority — not core loop |
| SSE endpoint not integration-tested with real EventSource client | Low | Unit tests cover route registration and event emission only |

## 17. Current Development Focus

- **Just completed (v0.6.1):**
  - PR #3 merged to main (MCP server, SSE, voice, replay)
  - UIA element overlay: PyQt6 transparent window, colour-coded bounding boxes, click-to-inspect, search, profile export
  - 4 new CLI commands: mcp, voice, replay, overlay
- **Phase 3 tasks 1-7 complete** — see `docs/superpowers/plans/2026-03-18-gui-voice-mcp.md`
- **Total test count:** 288 unit tests passing. Mypy: 0 errors (69 source files).
- **Next priorities (Phase 3 continued):**
  1. Electron GUI scaffold (electron-vite + React + shadcn/ui + Radix + cmdk)
  2. GUI core components (command palette, task input, status panel, action log, voice button)
  3. GUI polish + accessibility (NVDA testing, keyboard navigation, high contrast)
  - See `docs/superpowers/plans/2026-03-18-gui-voice-mcp.md` Tasks 8-10 for details

---

*This document is the authoritative architectural reference for WindowsAgent. All implementation decisions must align with the contracts defined here. Any deviation requires updating this document first.*
