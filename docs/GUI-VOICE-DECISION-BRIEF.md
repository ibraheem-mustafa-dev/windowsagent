# WindowsAgent GUI + Voice — Decision Brief

**Date:** 2026-03-18
**Research method:** Deep Research (8 parallel agents, 100+ sources, 3 phases)
**Prepared for:** Bean (Ibraheem Mustafa) / Small Giants Studio

---

## The Real Question

Not "should we build a GUI for WindowsAgent?" but rather: **what form factor turns a Python automation library into a product that owns the gap between AI agents and the Windows desktop?**

The research reveals that the GUI is not the product. The product is the semantic bridge — the fact that WindowsAgent reads UI elements by name, not by pixel. The GUI, voice, and MCP server are three delivery mechanisms for that same capability. The real decision is which delivery mechanisms to build, in what order, and for which audience first.

---

## The Insight

**Voice is a trap. The keyboard is the moat.**

Every competitor (Dragon, Windows Voice Access, Tauri-based tools) is chasing voice-first interaction. The research demolishes this:

1. Voice recognition fails 50-80% of the time for users with moderate-severe dysarthria — the very people who need accessibility tools most.
2. Porcupine's free tier caps at 3 monthly active users. Beyond that: ~$6,000/year. The open-source alternative (openWakeWord) works but adds integration risk.
3. Whisper hallucinates commands in noisy environments. Every destructive action needs a confirmation step, which defeats the speed advantage of voice.

Meanwhile, nobody has built a **keyboard-first semantic automation tool** for Windows. WindowsAgent already has the hard part: UIA tree parsing, app profiles, LLM grounding. The unfair advantage is not voice — it is that WindowsAgent knows what every button is called and what it does. Voice is a useful secondary input. The keyboard command palette is the primary interface.

One-line pitch: **"Reads the UI by name, not by pixel."**

---

## The Proven Edge

**Electron + React + shadcn/ui + existing FastAPI backend**

This is the validated, low-risk architecture:

- **Stack:** Electron (renderer) + Vite + React + TypeScript + shadcn/ui (Radix primitives) + cmdk (command palette)
- **Backend:** Existing FastAPI on localhost:7862. SSE for status streaming (sse-starlette). No WebSockets needed.
- **Security:** contextBridge with whitelisted IPC channels. safeStorage for API keys. Localhost binding only.
- **Accessibility:** Flat React SPA, no iframes. Manual screen reader toggle (Electron's auto-detection is broken since v37). WCAG 2.2 AA throughout.
- **Voice (secondary):** Python subprocess managed by FastAPI. openWakeWord (not Porcupine) + faster-whisper tiny.en int8 on CPU. Load models at startup (3-8s cold start). Confirmation step for destructive actions.
- **Progressive disclosure:** Two levels only (NN/G guidance). Layer 1: natural language input + live execution panel. Layer 2: UIA inspector + JSONL editor + plugin API.
- **Dark mode default** (82% preference for AI-heavy apps), with light mode available.

**Costs:**
- Windows code signing: ~$200-400/year (required — SmartScreen blocks unsigned apps)
- Electron disk footprint: 150MB+ (acceptable for an AT tool)
- RAM: 200-500MB typical, up to 1GB with voice models loaded

**Timeline:** 8-11 weeks for the full GUI with voice as secondary input.

**Confidence:** High. VS Code proves this architecture works for accessibility. shadcn/ui + Electron starter kits save roughly 2 weeks.

**Risks already mitigated:**
- Tauri ruled out (NVDA regression, issue #12901)
- pywebview ruled out (NVDA cannot navigate it, GitHub issue #545)
- PyQt6 ruled out (screen reader bugs at Qt framework level)
- Porcupine replaced with openWakeWord (Apache 2.0, no per-user cost)

---

## The Innovation Play

**Three plays that compound into a platform. Build order matters.**

### Play 1: MCP Server (1 week)

Expose WindowsAgent as an MCP server. Every existing MCP Windows server is a dumb pyautogui wrapper — screenshot, click coordinates, done. WindowsAgent would be the first MCP server with UIA grounding, app profiles, verification, and error recovery.

This is the fastest path to adoption. Claude Desktop, Cursor, and every MCP-compatible agent becomes a distribution channel. No GUI needed. No marketing budget. Developers find it, use it, and tell others.

**Risk:** Low. MCP is a well-documented protocol. WindowsAgent already has the FastAPI surface. This is mostly plumbing.

### Play 2: Floating Voice Pill (2-3 weeks, after MCP)

A 48px translucent always-on-top circle. Tap to speak. Visual feedback during processing. No window chrome. Sits in the corner like a system tray widget but with personality.

OpenAI is building this as hardware (the Jony Ive device, H2 2026). Nobody has done it as software on Windows. This is the demo that makes people share videos.

**Critical caveat:** Do NOT position this as an accessibility feature. Position it as a convenience feature. Voice fails too often for motor-impaired users to rely on it. The pill must have a keyboard shortcut equivalent (e.g., Ctrl+Space) that does the same thing without voice.

**Risk:** Medium. Always-on-top windows can conflict with full-screen apps and games. Voice latency on CPU is 500ms-2s — noticeable but acceptable. Whisper hallucination in noisy environments requires the confirmation step for anything destructive.

### Play 3: UIA Element Overlay (1-2 weeks, after Voice Pill)

Chrome DevTools inspect mode for any Windows application. Draw colour-coded bounding boxes over UIA elements. Click to inspect properties. Drag to define interaction zones. This is the killer feature for:

- Community profile authoring (contributors can SEE what the UIA tree exposes)
- Demos and marketing (visually proves WindowsAgent understands the UI)
- Debugging automation failures (see exactly what the agent sees)

**Risk:** Low-medium. Drawing overlays on other apps' windows requires Win32 layered windows or a transparent Electron overlay. Performance impact needs testing with complex UIA trees.

### Combined Build Order

1. MCP Server — 1 week. Immediate developer adoption channel.
2. Floating Voice Pill — 2-3 weeks. The demo that sells the product.
3. UIA Element Overlay — 1-2 weeks. The developer tool that builds community.
4. Full Electron GUI — remaining weeks. The consumer product.

**Total: 4-6 weeks for plays 1-3, then 4-5 weeks for the full GUI. 8-11 weeks total.**

---

## The Moonshot

**Voice-controlled, visually-inspectable MCP bridge between AI and Windows.**

Combine all three plays into a single platform where:
- Any AI agent (Claude, GPT, local models) controls Windows apps through MCP
- Users can speak commands through the Voice Pill or type them in the command palette
- The UIA overlay shows exactly what the agent sees and does, in real time
- Community profiles make every Windows app "smart" without per-app integration

Nobody has this combination. Microsoft's UFO2/UFO3 is the closest competitor (hybrid UIA + vision, open source) but has no voice, no consumer GUI, no MCP, and no community profile system.

**Positioning:** Do not call it an accessibility tool until you have evidence from disabled users that it works for them. Instead:

> "Desktop automation with keyboard and voice options. The semantic bridge between AI agents and Windows applications."

Let accessibility be earned through user evidence, not claimed through marketing.

**Risk:** High complexity. The moonshot only works if plays 1-3 each work independently first. Do not attempt to build them as an integrated system from day one.

---

## What We Ruled Out

| Option | Why it is dead |
|--------|---------------|
| Tauri | NVDA screen reader regression (issue #12901). Not fixed as of research date. |
| pywebview | NVDA cannot navigate it at all (GitHub issue #545). |
| PyQt6 | Screen reader bugs at the Qt framework level. Not fixable from application code. |
| Porcupine wake word | Free tier: 3 users. Beyond that: ~$6,000/year. Use openWakeWord (Apache 2.0). |
| Voice-first positioning | 50-80% WER for dysarthric speech. Whisper hallucinations in noise. Voice is secondary. |
| Dragon NaturallySpeaking integration | Dying product, breaks on updates, requires expensive microphones. |
| WebSockets for streaming | SSE is simpler, sufficient for one-way status updates, and already supported by FastAPI. |
| Three-level progressive disclosure | NN/G research is clear: maximum 2 levels or users get lost. |

---

## What Competitors Are Missing

1. **Microsoft UFO2/UFO3:** Powerful but research-only. No consumer GUI, no voice, no MCP, no community profiles. Requires technical users.
2. **Windows Voice Access:** Number-based overlay. User says "click 7." No semantic understanding. No natural language.
3. **Dragon NaturallySpeaking:** Dying. Expensive. Breaks on updates. No AI grounding.
4. **Power Automate:** Flowchart drag-and-drop. No natural language. No UIA intelligence.
5. **AutoHotkey:** Arcane syntax. Pixel-based. No AI. No semantic understanding.
6. **pyautogui MCP servers:** Screenshot + click coordinates. No UIA tree. No app profiles. No verification.

**The gap:** Nobody combines UIA semantic understanding + natural language + app profiles + MCP + community extensibility. WindowsAgent already has the first three. MCP and a GUI are engineering, not research.

---

## Risk of Inaction

1. Microsoft ships UFO3 with a consumer GUI. They have the UIA expertise, the distribution, and the budget. WindowsAgent's window closes.
2. The MCP ecosystem matures without a smart Windows bridge. Dumb pyautogui wrappers become "good enough" through sheer ecosystem momentum.
3. OpenAI ships the Jony Ive voice device and defines the form factor before WindowsAgent establishes the software-first version.
4. The open-source community profile system never reaches critical mass because there is no visual tooling (overlay) to make profile authoring easy.

Doing nothing is the highest-risk option. The safe Electron GUI without the innovation plays produces a competent but undifferentiated product.

---

## Business Model and Funding

**Pricing:**

| Tier | Price | What you get |
|------|-------|-------------|
| Core | Free, open source | MCP server, CLI, Python library, community profiles |
| Personal | 9/month | GUI, voice input, 3 app profiles, community profile access |
| Professional | 29/month | Unlimited profiles, UIA overlay, action recording/replay, priority support |
| Enterprise | Custom | On-premise, SSO, audit logging, custom profiles |

**UK Funding to pursue:**
- Access to Work: up to 66,000/year per employee (for accessibility positioning)
- Innovate UK Smart Grants: up to 500,000
- SBRI (Small Business Research Initiative): public sector automation contracts
- Digital Inclusion Innovation Fund: 7.2M pot for 2025/26

---

## Your Decision

### Option A: Innovation Stack (Recommended)

Build MCP server first (1 week), then Voice Pill (2-3 weeks), then UIA Overlay (1-2 weeks), then full Electron GUI (4-5 weeks). Total: 8-11 weeks.

| Criterion | Score |
|-----------|-------|
| Competitive advantage | 9/10 |
| Innovation | 9/10 |
| Feasibility | 7/10 |
| Time-to-value | 8/10 |

### Option B: Proven Edge Only

Build the Electron GUI with command palette and voice as secondary input. Skip MCP, Voice Pill, and Overlay for now. Total: 8-11 weeks.

| Criterion | Score |
|-----------|-------|
| Competitive advantage | 5/10 |
| Innovation | 3/10 |
| Feasibility | 9/10 |
| Time-to-value | 6/10 |

### Option C: MCP-First, GUI Later

Ship the MCP server in week 1. Gather developer feedback. Build the GUI based on what developers actually need. Total: 1 week to first release, GUI timeline TBD.

| Criterion | Score |
|-----------|-------|
| Competitive advantage | 7/10 |
| Innovation | 6/10 |
| Feasibility | 9/10 |
| Time-to-value | 10/10 |

**Recommendation: Option A.** The build order de-risks it — each play ships independently and delivers value before the next begins. MCP in week 1 gives immediate developer traction. The Voice Pill gives the demo video that sells the vision. The Overlay gives contributors the tooling to build profiles. The GUI ties it all together. Option B builds a product nobody talks about. Option C is smart but leaves the consumer opportunity on the table.

---

## Key Sources

1. Tauri NVDA regression — github.com/tauri-apps/tauri/issues/12901
2. pywebview NVDA failure — github.com/r0x0r/pywebview/issues/545
3. Electron accessibility regression (v37+) — github.com/electron/electron/issues/48039
4. Picovoice Porcupine pricing — picovoice.ai/pricing (3 MAU free tier)
5. openWakeWord — github.com/dscripka/openWakeWord (Apache 2.0)
6. Dysarthric speech WER — PMC (pmc.ncbi.nlm.nih.gov/articles/PMC10586392)
7. faster-whisper benchmarks — github.com/SYSTRAN/faster-whisper
8. shadcn/ui + Electron starter — github.com/LuanRoger/electron-shadcn
9. VS Code accessibility guidelines — github.com/microsoft/vscode/wiki/Accessibility-Guidelines
10. Microsoft UFO2/UFO3 — microsoft.github.io/UFO
11. NN/G progressive disclosure — nngroup.com/articles/progressive-disclosure
12. Access to Work scheme — up to 66K/year per disabled employee
13. Innovate UK Smart Grants — up to 500K
14. Digital Inclusion Innovation Fund — 7.2M for 2025/26
15. Agentic design patterns — agentic-design.ai/patterns/ui-ux-patterns
16. MCP Windows servers comparison — github.com/claude-did-this/MCPControl, github.com/mario-andreschak/mcp-windows-desktop-automation
17. Xbox Adaptive Controller design — news.microsoft.com/stories/xbox-adaptive-controller
18. Dragon NaturallySpeaking decline — gigcitygeek.com/2025/03/13/the-death-of-dragon-naturallyspeaking
19. WebView2 accessibility failure — github.com/MicrosoftEdge/WebView2Feedback/issues/2330
20. VoiceProcessingToolkit — pypi.org/project/VoiceProcessingToolkit
