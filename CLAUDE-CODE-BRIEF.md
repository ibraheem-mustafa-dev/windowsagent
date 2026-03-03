# WindowsAgent - Claude Code Architecture Brief

## Context

You are architecting **WindowsAgent**, an open-source AI agent that controls Windows desktop applications reliably. Read these docs first:
- `docs/PROJECT-BRIEF.md` - full project brief with architecture, milestones, competitive analysis
- `docs/research.md` - comprehensive research on the computer use agent landscape

## What already exists

There's a working prototype at `C:\Users\Bean\.openclaw\workspace\tools\desktop-agent\server.py` - a Flask API (port 7862) that combines pywinauto + pyautogui + pywinctl. It works for basic inspect/click/type but has these problems discovered in real usage:

1. **WebView2 apps fail** - New Outlook, Teams, VS Code are Edge WebView2 wrappers. The UIA tree only shows rendered/visible items. Virtualised lists (like email lists) don't expose offscreen items. `pyautogui.scroll()` doesn't reach the inner WebView.
2. **Focus management breaks** - Clicking an email shifts focus to the reading pane instead of staying in the email list. Need panel-aware focus tracking.
3. **No vision fallback** - When UIA tree is incomplete (virtualised lists, custom-rendered UIs), there's no fallback to screenshot + vision model analysis.
4. **No task planning** - It's a raw API. No LLM-driven task decomposition. User must manually chain actions.

## Your job

Build the architecture for WindowsAgent as a proper Python package. This will eventually be both:
1. An OpenClaw skill/tool (`windows_desktop`)
2. A standalone `pip install windowsagent` package

## Architecture to build

### Core: Observe-Plan-Act-Verify loop

```
User task (natural language)
    |
    v
[Task Planner] - LLM breaks task into steps
    |
    v
[Observer] - captures current state
    |-- UI Automation tree (pywinauto UIA backend)
    |-- Screenshot (mss or pyautogui)
    |-- OCR text extraction (Windows OCR API)
    |
    v
[Grounder] - matches planned action to UI element
    |-- Primary: UIA tree element matching (by name, type, automation_id)
    |-- Fallback: Vision model (Gemini Flash or Claude Haiku) analyses screenshot
    |-- OCR fallback: text coordinate mapping
    |
    v
[Actor] - executes the action
    |-- UIA patterns (Invoke, SelectionItem, Value, ScrollItem, etc.)
    |-- Fallback: pyautogui coordinate click/type
    |-- Keyboard shortcuts when faster than UI navigation
    |
    v
[Verifier] - confirms action succeeded
    |-- Screenshot comparison (before/after)
    |-- UIA tree state check (element changed?)
    |-- Vision model confirmation if needed
    |
    v
Loop or report completion/failure
```

### Package structure

```
windowsagent/
├── __init__.py
├── agent.py              # Main agent class - orchestrates the loop
├── observer/
│   ├── __init__.py
│   ├── uia.py            # UI Automation tree inspection (pywinauto)
│   ├── screenshot.py     # Fast screen/window capture (mss)
│   ├── ocr.py            # Windows OCR API or Tesseract
│   └── state.py          # Combined state representation
├── planner/
│   ├── __init__.py
│   ├── task_planner.py   # LLM-based task decomposition
│   └── prompts.py        # System prompts for planning
├── grounder/
│   ├── __init__.py
│   ├── uia_grounder.py   # Match action to UIA element
│   ├── vision_grounder.py # Vision model fallback
│   └── hybrid.py         # Try UIA first, fall back to vision
├── actor/
│   ├── __init__.py
│   ├── uia_actor.py      # Execute via UIA patterns
│   ├── input_actor.py    # Fallback mouse/keyboard via pyautogui
│   └── clipboard.py      # Efficient data transfer via clipboard
├── verifier/
│   ├── __init__.py
│   └── verify.py         # Confirm action succeeded
├── apps/                 # App-specific profiles
│   ├── __init__.py
│   ├── base.py           # Base app profile
│   ├── outlook.py        # Outlook-specific handling (WebView2 workarounds)
│   ├── excel.py          # Excel automation helpers
│   ├── file_explorer.py  # File Explorer shortcuts
│   └── generic.py        # Generic app handler
├── server.py             # HTTP API (Flask/FastAPI) for OpenClaw integration
├── cli.py                # CLI interface
└── config.py             # Configuration (models, timeouts, etc.)

tests/
├── test_observer.py
├── test_grounder.py
├── test_actor.py
└── test_apps/
    ├── test_notepad.py
    ├── test_excel.py
    └── test_file_explorer.py
```

### Key design decisions

1. **UIA-first, always.** Try the accessibility tree before touching vision models. It's faster, cheaper, and more reliable. Only fall back to vision when UIA tree is incomplete or missing.

2. **App profiles for known apps.** Outlook, Excel, File Explorer each get a profile that knows their quirks:
   - Outlook: WebView2 virtualised lists need special scroll handling (Page Down key, not mouse scroll)
   - Excel: Cell addressing via Name Box is faster than clicking
   - File Explorer: Address bar navigation is faster than clicking through folders

3. **Panel-aware focus tracking.** Before acting, identify which panel has focus. After acting, verify focus didn't jump to wrong panel. Key for apps like Outlook with reading pane.

4. **Scroll strategies per app type:**
   - Native Win32: `pyautogui.scroll()` works
   - UWP/WinUI: UIA ScrollPattern
   - WebView2: Page Down/Up keys, or find scrollbar element
   - Fallback: Click in target area, then keyboard scroll

5. **Verification is not optional.** Every action gets verified. Screenshot diff or UIA state check. If verification fails, retry once, then report failure.

6. **Vision model is Gemini Flash by default.** Cheapest, fastest, good enough for UI grounding. User can override to Claude Sonnet/Haiku if preferred.

7. **The HTTP API stays.** OpenClaw calls it via localhost. But also add a Python API for direct use:
   ```python
   from windowsagent import Agent
   agent = Agent()
   agent.run("Open Excel, create a new spreadsheet, put sales data in column A")
   ```

### Critical WebView2 handling

WebView2 apps (new Outlook, Teams, VS Code) are the #1 reliability problem. Strategy:

```python
class WebView2Handler:
    """Special handling for Edge WebView2 apps."""
    
    def detect_webview2(self, window) -> bool:
        """Check if window contains WebView2 by looking for 
        Chrome_WidgetWin_1 or similar class names."""
        pass
    
    def scroll_content(self, window, direction, amount):
        """WebView2 scroll: click in target area, then Page Down/Up.
        Mouse wheel doesn't reach the inner content."""
        # 1. Click in the content area to ensure focus
        # 2. Use Page Down/Up keys (works reliably)
        # 3. Verify scroll happened via screenshot diff
        pass
    
    def find_virtualised_items(self, window, target_text):
        """For virtualised lists: scroll + inspect loop.
        Items only appear in UIA tree when scrolled into view."""
        # 1. Get currently visible items from UIA tree
        # 2. Check if target is visible
        # 3. If not, scroll down one page
        # 4. Re-inspect UIA tree
        # 5. Repeat until found or bottom reached
        pass
```

### OpenClaw integration

Create an OpenClaw skill at `~/.openclaw/workspace/skills/windows-desktop/SKILL.md` that:
- Documents all available actions
- Shows example usage
- Points to the localhost API
- Explains when to use this vs browser tool vs unbrowse_desktop

The HTTP API should match this interface:
```
POST /task     - natural language task execution (full agent loop)
POST /observe  - get current window state (UIA tree + screenshot)
POST /act      - execute a single action
POST /verify   - check if last action succeeded
GET  /windows  - list all windows
GET  /health   - service health check
```

## What to build first (Phase 1)

1. **Package scaffold** - pyproject.toml, directory structure, dependencies
2. **Observer module** - UIA tree + screenshot capture working reliably
3. **Actor module** - click, type, scroll, keyboard shortcuts
4. **WebView2 handler** - special scroll and virtualised list support
5. **App profiles** - Notepad (simple test), File Explorer, Outlook (WebView2 test)
6. **HTTP API** - upgraded from existing Flask server
7. **Tests** - one test per app profile that runs a real task

Do NOT build the task planner or vision grounder yet. Get the foundation solid first. The LLM layer can be added on top once observe/act/verify works reliably.

## Dependencies

```toml
[project]
name = "windowsagent"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "pywinauto>=0.6.8",
    "pyautogui>=0.9.54",
    "pywinctl>=0.4",
    "mss>=9.0",
    "Pillow>=10.0",
    "flask>=3.0",
]

[project.optional-dependencies]
vision = ["google-generativeai>=0.4", "anthropic>=0.18"]
ocr = ["pytesseract>=0.3"]
dev = ["pytest>=7.0", "pytest-cov"]
```

## Success criteria for Phase 1

1. `python -m windowsagent.cli observe --window "Notepad"` returns a clean UIA tree + screenshot
2. `python -m windowsagent.cli act --window "Notepad" --action type --text "Hello"` types text
3. Outlook email list scrolls reliably (WebView2 handler works)
4. File Explorer navigates to a folder by path
5. HTTP API on localhost serves all endpoints
6. All tests pass on Windows 11

## Start now

Begin with the package scaffold and observer module. Get `uia.py` and `screenshot.py` working first - everything else depends on being able to see what's on screen.
