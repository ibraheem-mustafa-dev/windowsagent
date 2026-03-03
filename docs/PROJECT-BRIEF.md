# WindowsAgent - Project Brief

**Date:** 2026-02-23
**Owner:** Ibraheem (Bean) Mustafa / Small Giants Studio
**Codename:** WindowsAgent
**Status:** Research complete, prototyping phase

---

## One-liner

Open-source AI agent that controls Windows desktop apps like a human would, but reliably.

## Problem

AI desktop automation is broken on Windows:

- **Claude Computer Use** takes screenshots and guesses where to click. Works sometimes, fails often. Linux-focused.
- **OpenAI Operator** only does browsers. No desktop apps.
- **Google Mariner** Chrome extension only. $250/mo.
- **Open Interpreter** bolted GUI automation onto a code execution tool. Not its strength.
- **PyAutoGUI scripts** break the moment a window moves 3 pixels.

Meanwhile, 85%+ of enterprise desktops run Windows. Every business has staff doing repetitive tasks in Excel, Outlook, Teams, and proprietary Windows apps that have zero API access.

Nobody has built a reliable, open-source agent that properly controls Windows applications.

## Solution

**WindowsAgent** uses the Windows UI Automation API (the same system screen readers use) to understand what's on screen. Instead of guessing pixel coordinates from screenshots, it reads the actual accessibility tree: button names, text fields, menu items, their exact positions.

When an app doesn't expose accessibility info (legacy/custom apps), it falls back to a vision model (Gemini or Claude) analysing a screenshot.

**The hybrid approach:**
1. Try UI Automation API first (fast, reliable, precise)
2. Fall back to vision model + OCR (slower but works on anything)
3. Execute via pywinauto (mouse, keyboard, app control)

## Architecture

```
User task ("Send an email to Amir about the invoice")
    |
    v
[Task Planner] — breaks into steps using LLM
    |
    v
[Observe] — UI Automation tree + screenshot
    |
    v
[Ground] — match step to UI element (accessibility tree or vision)
    |
    v
[Act] — pywinauto click/type/key
    |
    v
[Verify] — screenshot confirms action worked
    |
    v
Loop until done or error
```

### Core components

| Component | Tech | Purpose |
|-----------|------|---------|
| Element targeting | pywinauto + UI Automation API | Find buttons, fields, menus by name/type |
| Vision fallback | Gemini 2.5 Flash / Claude Sonnet | Identify elements when accessibility fails |
| OCR layer | Windows OCR API or Tesseract | Read text from screen |
| Action execution | pywinauto | Click, type, keyboard shortcuts |
| Screenshots | mss (Python) | Fast screen capture for vision model |
| Task planning | Claude/Gemini | Break natural language into steps |
| OpenClaw integration | Skill + tool definition | Expose as `windows_desktop` tool |

### Key design decisions

1. **Accessibility-first, not vision-first.** Vision models hallucinate coordinates. Accessibility APIs give exact positions. Use the reliable thing first.
2. **Hybrid grounding.** Some apps have great accessibility trees (Office, Edge). Some have none (games, custom C++ apps). Support both.
3. **Verify after every action.** Screenshot after each step to confirm it worked. Retry or ask for help if not.
4. **OpenClaw-native.** Not a standalone app initially. Ships as an OpenClaw skill, uses existing agent orchestration.

## Target apps (Phase 1)

| App | Accessibility quality | Use case |
|-----|----------------------|----------|
| File Explorer | Excellent | File management, organisation |
| Notepad/VS Code | Good | Text editing, code |
| Excel | Excellent | Data entry, reports |
| Outlook | Good | Email automation |
| Chrome/Edge | Good | Supplement browser tool |
| Teams | Moderate | Meeting scheduling, messages |

## Competitive advantage

| Feature | WindowsAgent | Claude CU | Operator | Mariner | Open Interpreter |
|---------|-------------|-----------|----------|---------|-----------------|
| Windows-native | Yes | Linux VM | No | No | Partial |
| Accessibility API | Yes | No | No | No | No |
| Vision fallback | Yes | Only method | N/A | Yes | Yes |
| Open source | Yes | No | No | No | Yes |
| Desktop apps | Yes | Yes | No | No | Yes |
| Reliability | High (API-based) | Medium (vision) | N/A | Medium | Low |
| Cost | Free (own API keys) | API pricing | $200/mo | $250/mo | Free |

## Revenue model (if productised)

**Phase 1: OpenClaw skill (free)**
- Drives OpenClaw adoption
- Community contributions
- Establishes credibility

**Phase 2: Standalone agent (open-source + hosted)**
- Open-source core (MIT)
- Hosted version with managed cloud VMs ($29-99/mo)
- Enterprise: on-prem deployment + custom app integrations
- Marketplace: user-contributed "recipes" for specific workflows

**Phase 3: Platform**
- Record-and-replay: user demonstrates task, agent learns and repeats
- Multi-agent: one agent does Excel while another does email
- Scheduled automation: cron-triggered desktop tasks

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| UI Automation API coverage varies by app | High | Vision fallback covers gaps |
| Windows updates break accessibility tree | Medium | Version-specific testing, community reports |
| Vision model costs add up | Medium | Cache screenshots, use Flash not Pro |
| Scope creep (trying to automate everything) | High | Phase 1 is 6 apps only |
| Competition ships faster | Medium | Our hybrid approach is genuinely better |

## Milestones

### Phase 1: Prototype (Weeks 1-2)
- [ ] Install pywinauto, mss, test accessibility tree on 3 apps
- [ ] Build `windows_desktop` OpenClaw tool with basic actions (click, type, read)
- [ ] Demo: "Open Notepad, type hello, save as test.txt"
- [ ] Demo: "Open Excel, enter data in cells A1-A5"

### Phase 2: Expand (Month 1-2)
- [ ] Add vision fallback for apps with poor accessibility
- [ ] Support 10+ apps (full Office suite, Teams, VS Code, browsers)
- [ ] Multi-step task planning ("Send Amir the Q4 report by email")
- [ ] Error recovery and retry logic
- [ ] Record-and-replay prototype

### Phase 3: Release (Month 3+)
- [ ] Package as standalone skill on ClawHub
- [ ] Documentation and examples
- [ ] GitHub repo (open source)
- [ ] Community testing and feedback
- [ ] Blog post / demo video for marketing

## Budget

| Item | Cost | Notes |
|------|------|-------|
| Development | Bean's time | No external cost |
| API calls (vision model) | ~$5-20/mo testing | Gemini Flash is cheap |
| pywinauto | Free (MIT) | Open source |
| mss | Free (MIT) | Open source |
| GitHub repo | Free | Public repo |
| Total Phase 1 | $0-20 | Just API costs for testing |

## Success criteria

1. **Reliability:** 90%+ success rate on simple tasks across target apps
2. **Speed:** Faster than doing it manually for multi-step tasks
3. **Adoption:** 50+ ClawHub installs in first month
4. **Differentiation:** Demonstrably more reliable than screenshot-only approaches

---

*Research: memory/research/computer-use-agents.md*
*Registry: memory/projects-registry.md (Priority 6)*
