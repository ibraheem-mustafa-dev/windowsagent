# WindowsAgent Skills

Ready-to-use AI skills for WindowsAgent. Control Windows desktop apps from any AI platform.

## Platform Support

| Platform | Location | Format |
|----------|----------|--------|
| OpenClaw | `skills/openclaw/` | SKILL.md |
| Claude Desktop | `skills/mcp/` | MCP stdio bridge |
| Cursor | `skills/cursor/` | .mdc rules file |

## Quick Setup

### OpenClaw

Copy the skill folders into your OpenClaw workspace:

```powershell
Copy-Item -Recurse skills/openclaw/* %USERPROFILE%/.openclaw/workspace/skills/
```

Each skill is self-contained — OpenClaw picks them up automatically by folder name.

### Claude Desktop

1. Install dependencies:
   ```bash
   pip install mcp httpx
   ```

2. Add to your `claude_desktop_config.json` (Settings > Developer > Edit Config):
   ```json
   {
     "mcpServers": {
       "windowsagent": {
         "command": "python",
         "args": ["C:/path/to/skills/mcp/bridge.py"],
         "env": {
           "WA_BASE_URL": "http://localhost:7862"
         }
       }
     }
   }
   ```

3. Start WindowsAgent: `windowsagent serve`

4. Restart Claude Desktop. You'll see 6 new tools: `wa_observe`, `wa_act`, `wa_task`, `wa_shell`, `wa_spawn`, `wa_health`.

### Cursor

1. Copy `skills/cursor/windowsagent.mdc` to your project's `.cursor/rules/` directory:
   ```powershell
   mkdir -p .cursor/rules
   Copy-Item skills/cursor/windowsagent.mdc .cursor/rules/
   ```

2. Start WindowsAgent: `windowsagent serve`

3. Cursor now has context about all WindowsAgent endpoints, element names, and patterns.

## Available App Skills (OpenClaw)

| Skill | Description |
|-------|-------------|
| `windowsagent-chrome` | Open URLs, navigate tabs, read pages, fill forms |
| `windowsagent-edge` | Same as Chrome (identical UIA structure) |
| `windowsagent-vscode` | Open projects, switch files, run terminal, Claude Code |
| `windowsagent-teams` | Navigate channels, read/send messages, call controls |
| `windowsagent-powershell` | Run commands, manage processes, terminal control |
| `windowsagent-whatsapp` | Read messages via OCR, stage messages for review |
| `windowsagent-outlook` | Read/send email via himalaya, Outlook UIA shortcuts |
| `windowsagent-explorer` | File ops via shell, Explorer UIA, Save/Open dialogs |
| `windowsagent-clipboard` | Read/write clipboard, paste into any app |
| `windowsagent-screenshot` | Capture windows, OCR text, save to file |
| `windowsagent-notepad` | Open, type, read, save, clear — primary test target |

## How It Works

The skills are built on top of WindowsAgent's app profiles (`windowsagent/apps/`). Each profile contains verified UIA element names and keyboard shortcuts for that app.

WindowsAgent reads the Windows UI Automation accessibility tree — the same API that screen readers use — to find and interact with UI elements by name, not by pixel coordinates. This makes actions reliable regardless of window position, DPI scaling, or theme.

See [ARCHITECTURE.md](../ARCHITECTURE.md) for the full technical specification.
