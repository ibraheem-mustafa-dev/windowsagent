# WindowsAgent

Open-source AI agent that controls Windows desktop apps like a human would, but reliably.

Uses Windows UI Automation API (via pywinauto) as primary element targeting, with vision model fallback for legacy apps. Integrates into OpenClaw as a `windows_desktop` tool.

## Status

Research complete. Ready to prototype.

## Docs

- [Project Brief](docs/PROJECT-BRIEF.md)
- [Research Report](docs/research.md)

## Quick Start

Coming soon. Phase 1 prototype in progress.

## Architecture

1. **UI Automation API** (pywinauto) — reads accessibility tree for reliable element targeting
2. **Vision model fallback** (Gemini/Claude) — for apps without accessibility info
3. **Action execution** (pywinauto) — mouse, keyboard, app control
4. **Verify loop** — screenshot after each action to confirm success

## Why not just use Claude Computer Use?

- Claude CU is Linux-focused, screenshot-only, guesses pixel coordinates
- WindowsAgent reads actual button names and positions from the OS
- 85%+ of enterprise desktops are Windows
- This is free and open source

## License

MIT
