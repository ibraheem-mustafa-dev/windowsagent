# WindowsAgent

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4.svg)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-v0.1.0-blue.svg)](https://pypi.org/project/windowsagent/)

Open-source AI agent that controls Windows desktop applications using the accessibility tree — not pixel guessing.

---

## Why not just use Claude Computer Use?

Every other desktop AI agent works by taking a screenshot, sending it to a vision model, and hoping it guesses the right coordinates to click. This breaks constantly:

- Move a window 3 pixels — coordinates drift
- Scroll a list — everything shifts
- Use Outlook — virtualised list items are invisible to screenshots

**WindowsAgent reads the actual accessibility tree.** The same API that screen readers use. It knows the button is called "Send", exactly where it is, and whether it's enabled — without ever looking at the screen.

When the accessibility tree is incomplete (legacy apps, WebView2 content), it falls back to a vision model. But the primary path is fast, precise, and free.

| Feature | WindowsAgent | Claude CU | Operator | UI-TARS |
|---------|-------------|-----------|----------|---------|
| Windows-native | Yes | Linux VM | No | Cross-platform |
| Accessibility API | **Yes** | No | No | No |
| Vision fallback | Yes | Only method | N/A | Only method |
| Open source | **Yes** | No | No | Yes |
| Desktop apps | **Yes** | Yes | No | Yes |
| `pip install` | **Yes** | No | No | Complex setup |
| Reliability | **High** | Medium | N/A | Medium |
| Cost | **Free** | API pricing | $200/mo | Free |

---

## Quick Start

```bash
pip install windowsagent
```

Open Notepad and type some text:

```python
from windowsagent import Agent

agent = Agent()
agent.act("Notepad", action="type", target="Text Editor", params={"text": "Hello, World!"})
```

That's it. No coordinates. No screenshots. It finds the edit control by name.

---

## CLI Examples

List all visible windows:
```bash
windowsagent windows
```

Inspect the accessibility tree of any window:
```bash
windowsagent observe --window "Notepad"
```

Type text into a window:
```bash
windowsagent act --window "Notepad" --action type --element "Text Editor" --text "Hello"
```

Navigate File Explorer:
```bash
windowsagent act --window "File Explorer" --action key --keys "alt,d"
windowsagent act --window "File Explorer" --action type --element "Address Bar" --text "C:\\"
```

Start the HTTP server (for OpenClaw and other integrations):
```bash
windowsagent serve
# Server available at http://127.0.0.1:7862
```

---

## HTTP API

Once running (`windowsagent serve`), the API accepts:

```bash
# Health check
GET  http://localhost:7862/health

# List windows
GET  http://localhost:7862/windows

# Observe window state
POST http://localhost:7862/observe
{"window": "Notepad"}

# Execute an action
POST http://localhost:7862/act
{"window": "Notepad", "action": "type", "element": "Text Editor", "params": {"text": "Hello"}}

# Verify a change occurred
POST http://localhost:7862/verify
{"window": "Notepad"}
```

---

## Architecture

WindowsAgent uses a four-stage pipeline:

```
Observe → Ground → Act → Verify
```

1. **Observe** — reads the Windows UI Automation accessibility tree + captures screenshot
2. **Ground** — matches your description ("the Send button") to a real UI element
3. **Act** — executes via UIA patterns (Invoke, Value, Scroll, etc.) or keyboard fallback
4. **Verify** — screenshot diff confirms the action worked

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical specification.

---

## Supported Apps

| App | Status | Notes |
|-----|--------|-------|
| Notepad | Stable | Primary test target |
| File Explorer | Stable | Navigate, list, create, rename, delete |
| Outlook (new) | Beta | WebView2 scroll support, virtualised email lists |
| Generic Win32 | Stable | Any app with a standard accessibility tree |
| WebView2 apps | Beta | Teams, VS Code, any Electron app |

Community-contributed profiles live in [`profiles/community/`](profiles/community/). See [CONTRIBUTING.md](.github/CONTRIBUTING.md) to add your own.

---

## Installation

### Basic (UIA + screenshots only)

```bash
pip install windowsagent
```

### With vision fallback (Gemini or Claude)

```bash
pip install "windowsagent[vision]"

# Set your API key
export GEMINI_API_KEY=your_key_here
# or
export ANTHROPIC_API_KEY=your_key_here
```

### With OCR

```bash
pip install "windowsagent[ocr]"
# Also requires Tesseract: https://github.com/tesseract-ocr/tesseract
```

### Full install

```bash
pip install "windowsagent[vision,ocr]"
```

---

## Configuration

WindowsAgent reads config from (highest priority wins):

1. Environment variables: `WINDOWSAGENT_<SETTING>=value`
2. `pyproject.toml` `[tool.windowsagent]` section
3. `~/.windowsagent/config.json`
4. Defaults

Common settings:

```bash
# Choose vision model
WINDOWSAGENT_VISION_MODEL=gemini-flash  # or claude-haiku, claude-sonnet, none

# Adjust timeouts
WINDOWSAGENT_UIA_TIMEOUT=10.0
WINDOWSAGENT_VERIFY_TIMEOUT=5.0

# Disable sensitive action confirmation
WINDOWSAGENT_CONFIRM_SENSITIVE=false

# Change log level
WINDOWSAGENT_LOG_LEVEL=DEBUG
```

---

## Roadmap

**Phase 1 (current):** Foundation
- Observe/Act/Verify pipeline
- Notepad, File Explorer, Outlook app profiles
- HTTP API on localhost
- CLI interface

**Phase 2:** Vision + Reliability
- Gemini Flash vision grounding for apps with poor accessibility
- DPI scaling at 100% and 150%
- Excel profile
- Replay video recording (`--record` flag)
- Community app profile system

**Phase 3:** LLM Task Planning
- Natural language task execution (`agent.run("Open Notepad and type my notes")`)
- Error recovery (focus loss, unexpected dialogs)
- Plugin hooks (`on_observe`, `on_act`)

**Phase 4:** Record & Replay
- Record user actions into replayable JSON
- Variable substitution in replays
- Local VLM support (Ollama + UI-TARS)
- Workflow marketplace

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for how to:
- Report bugs
- Submit app profiles for new Windows applications
- Add features

App profiles are especially welcome — each one extends WindowsAgent's reach to a new application.

---

## Requirements

- Windows 10 (build 1903+) or Windows 11
- Python 3.10+
- pywinauto, pyautogui, mss, Pillow, FastAPI

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built by [Small Giants Studio](https://smallgiants.studio) · Open source · Windows-first*
