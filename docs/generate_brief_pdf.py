"""Generate ADHD-friendly PDF brief for WindowsAgent GUI + Voice decision."""

import sys

sys.stdout.reconfigure(encoding="utf-8")

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    KeepTogether,
)


# ── Colours ──────────────────────────────────────────────────────────────────

DARK_BG = HexColor("#0A0A0F")
ACCENT_BLUE = HexColor("#3B82F6")
ACCENT_GREEN = HexColor("#22C55E")
ACCENT_RED = HexColor("#EF4444")
ACCENT_AMBER = HexColor("#F59E0B")
ACCENT_PURPLE = HexColor("#A855F7")
GREY_TEXT = HexColor("#94A3B8")
LIGHT_TEXT = HexColor("#E2E8F0")
WHITE_TEXT = HexColor("#F8FAFC")
CARD_BG = HexColor("#1E293B")
CARD_BORDER = HexColor("#334155")
SURFACE = HexColor("#0F172A")


# ── Styles ───────────────────────────────────────────────────────────────────

styles = getSampleStyleSheet()

s_title = ParagraphStyle(
    "BriefTitle",
    fontName="Helvetica-Bold",
    fontSize=28,
    leading=34,
    textColor=WHITE_TEXT,
    spaceAfter=4 * mm,
)

s_subtitle = ParagraphStyle(
    "BriefSubtitle",
    fontName="Helvetica",
    fontSize=12,
    leading=16,
    textColor=GREY_TEXT,
    spaceAfter=8 * mm,
)

s_section = ParagraphStyle(
    "SectionHead",
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    textColor=ACCENT_BLUE,
    spaceBefore=10 * mm,
    spaceAfter=4 * mm,
)

s_subsection = ParagraphStyle(
    "SubsectionHead",
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=18,
    textColor=WHITE_TEXT,
    spaceBefore=6 * mm,
    spaceAfter=3 * mm,
)

s_body = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=11,
    leading=16,
    textColor=LIGHT_TEXT,
    spaceAfter=3 * mm,
)

s_body_bold = ParagraphStyle(
    "BodyBold",
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=16,
    textColor=WHITE_TEXT,
    spaceAfter=3 * mm,
)

s_callout = ParagraphStyle(
    "Callout",
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=18,
    textColor=ACCENT_GREEN,
    spaceBefore=4 * mm,
    spaceAfter=4 * mm,
    leftIndent=8 * mm,
    borderPadding=(4 * mm, 4 * mm, 4 * mm, 4 * mm),
)

s_warning = ParagraphStyle(
    "Warning",
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=16,
    textColor=ACCENT_RED,
    spaceAfter=3 * mm,
    leftIndent=4 * mm,
)

s_bullet = ParagraphStyle(
    "Bullet",
    fontName="Helvetica",
    fontSize=11,
    leading=16,
    textColor=LIGHT_TEXT,
    spaceAfter=2 * mm,
    leftIndent=8 * mm,
    bulletIndent=4 * mm,
)

s_number = ParagraphStyle(
    "NumberedItem",
    fontName="Helvetica",
    fontSize=11,
    leading=16,
    textColor=LIGHT_TEXT,
    spaceAfter=2 * mm,
    leftIndent=8 * mm,
)

s_table_header = ParagraphStyle(
    "TableHeader",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=WHITE_TEXT,
)

s_table_cell = ParagraphStyle(
    "TableCell",
    fontName="Helvetica",
    fontSize=10,
    leading=13,
    textColor=LIGHT_TEXT,
)

s_table_cell_bold = ParagraphStyle(
    "TableCellBold",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=WHITE_TEXT,
)

s_score = ParagraphStyle(
    "Score",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=ACCENT_GREEN,
    alignment=TA_CENTER,
)

s_score_mid = ParagraphStyle(
    "ScoreMid",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=ACCENT_AMBER,
    alignment=TA_CENTER,
)

s_score_low = ParagraphStyle(
    "ScoreLow",
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=13,
    textColor=ACCENT_RED,
    alignment=TA_CENTER,
)

s_footer = ParagraphStyle(
    "Footer",
    fontName="Helvetica",
    fontSize=8,
    leading=10,
    textColor=GREY_TEXT,
    alignment=TA_RIGHT,
)

s_pitch = ParagraphStyle(
    "Pitch",
    fontName="Helvetica-Bold",
    fontSize=16,
    leading=22,
    textColor=ACCENT_PURPLE,
    spaceBefore=4 * mm,
    spaceAfter=6 * mm,
    alignment=TA_CENTER,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def hr():
    return HRFlowable(
        width="100%", thickness=0.5, color=CARD_BORDER,
        spaceBefore=4 * mm, spaceAfter=4 * mm,
    )


def make_table(headers, rows, col_widths=None):
    """Build a styled table with dark theme."""
    header_cells = [Paragraph(h, s_table_header) for h in headers]
    data = [header_cells]
    for row in rows:
        data.append(row)

    w = col_widths or [None] * len(headers)
    t = Table(data, colWidths=w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CARD_BG),
        ("BACKGROUND", (0, 1), (-1, -1), SURFACE),
        ("TEXTCOLOR", (0, 0), (-1, -1), LIGHT_TEXT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def bg_canvas(canvas, doc):
    """Draw dark background on every page."""
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)
    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY_TEXT)
    canvas.drawRightString(
        A4[0] - 20 * mm, 10 * mm,
        f"WindowsAgent GUI + Voice Brief  |  Page {doc.page}",
    )
    canvas.drawString(
        20 * mm, 10 * mm,
        "Small Giants Studio  |  2026-03-18",
    )
    canvas.restoreState()


# ── Build ────────────────────────────────────────────────────────────────────

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    story = []
    pw = A4[0] - 40 * mm  # printable width

    # ── Cover ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph("WindowsAgent", s_title))
    story.append(Paragraph("GUI + Voice Command Brief", ParagraphStyle(
        "Title2", parent=s_title, fontSize=22, leading=28, textColor=ACCENT_BLUE,
    )))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Decision brief for Bean  /  Small Giants Studio  /  March 2026",
        s_subtitle,
    ))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        '"Reads the UI by name, not by pixel."',
        s_pitch,
    ))
    story.append(Spacer(1, 10 * mm))
    story.append(hr())
    story.append(Spacer(1, 6 * mm))

    # Research summary
    story.append(Paragraph("Research depth", s_subsection))
    story.append(Paragraph(
        "8 parallel research agents. 100+ sources. Reddit, GitHub, Hacker News, "
        "peer-reviewed studies, official docs, first-person accounts. "
        "Three phases: understand, attack from every angle, verify.",
        s_body,
    ))

    story.append(PageBreak())

    # ── Page 2: The Insight ──────────────────────────────────────────────
    story.append(Paragraph("1. The Insight", s_section))
    story.append(Paragraph(
        "Voice is a trap. The keyboard is the moat.",
        s_callout,
    ))

    story.append(Paragraph(
        "Every competitor chases voice-first interaction. The research demolishes this:",
        s_body,
    ))

    story.append(Paragraph(
        "<bullet>&bull;</bullet> Voice recognition fails <b>50-80%</b> of the time for users with "
        "moderate-severe dysarthria. These are the people who need accessibility tools most.",
        s_bullet,
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> Porcupine wake word detection costs <b>$6,000/year</b> beyond 3 users. "
        "The open-source alternative (openWakeWord) works but adds integration risk.",
        s_bullet,
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> Whisper <b>hallucinates commands</b> in noisy environments. "
        "Every destructive action needs a confirmation step.",
        s_bullet,
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "WindowsAgent's unfair advantage is not voice. It is that WindowsAgent "
        "knows what every button is called and what it does. Nobody else reads "
        "the UI Automation tree semantically with LLM grounding and app profiles.",
        s_body_bold,
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Voice is a useful secondary input. The keyboard command palette is the primary interface.",
        s_body,
    ))

    story.append(hr())

    # ── The Gap ──────────────────────────────────────────────────────────
    story.append(Paragraph("2. The Gap Nobody Fills", s_section))

    gap_data = [
        [Paragraph("Dragon NaturallySpeaking", s_table_cell_bold),
         Paragraph("Dying. $699. Breaks on updates. No AI.", s_table_cell)],
        [Paragraph("Windows Voice Access", s_table_cell_bold),
         Paragraph("Number-based overlay. User says 'click 7'. No semantic understanding.", s_table_cell)],
        [Paragraph("Power Automate", s_table_cell_bold),
         Paragraph("Flowchart drag-and-drop. No natural language. No UIA.", s_table_cell)],
        [Paragraph("AutoHotKey", s_table_cell_bold),
         Paragraph("Arcane syntax. Pixel-based. No AI. No semantic understanding.", s_table_cell)],
        [Paragraph("Microsoft UFO2/UFO3", s_table_cell_bold),
         Paragraph("Research-only. No GUI. No voice. No MCP. No community profiles.", s_table_cell)],
        [Paragraph("pyautogui MCP servers", s_table_cell_bold),
         Paragraph("Screenshot + click coordinates. No UIA. No profiles. No verification.", s_table_cell)],
    ]
    story.append(make_table(
        ["Competitor", "Why they fail"],
        gap_data,
        col_widths=[pw * 0.3, pw * 0.7],
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Nobody combines UIA semantic understanding + natural language + app profiles "
        "+ MCP + community extensibility. WindowsAgent already has the first three.",
        s_body_bold,
    ))

    story.append(PageBreak())

    # ── Page 3: The Stack ────────────────────────────────────────────────
    story.append(Paragraph("3. The Tech Stack", s_section))
    story.append(Paragraph(
        "Proven. Accessible. Ships with starter kits.",
        s_body,
    ))

    stack_data = [
        [Paragraph("Shell", s_table_cell_bold),
         Paragraph("Electron", s_table_cell_bold),
         Paragraph("VS Code proves it works for accessibility. Tauri has NVDA bugs. PyQt has screen reader bugs.", s_table_cell)],
        [Paragraph("UI", s_table_cell_bold),
         Paragraph("React + shadcn/ui", s_table_cell_bold),
         Paragraph("Radix primitives = WCAG 2.2 AA out of the box. Dark mode default.", s_table_cell)],
        [Paragraph("Build", s_table_cell_bold),
         Paragraph("Vite + TypeScript", s_table_cell_bold),
         Paragraph("Fast dev server. Type-safe. electron-vite starter kit saves 2 weeks.", s_table_cell)],
        [Paragraph("Backend", s_table_cell_bold),
         Paragraph("Existing FastAPI", s_table_cell_bold),
         Paragraph("Already built. SSE for streaming status. No new server needed.", s_table_cell)],
        [Paragraph("Wake word", s_table_cell_bold),
         Paragraph("openWakeWord", s_table_cell_bold),
         Paragraph("Apache 2.0. No per-user cost. Replaces Porcupine ($6K/year).", s_table_cell)],
        [Paragraph("Voice STT", s_table_cell_bold),
         Paragraph("faster-whisper", s_table_cell_bold),
         Paragraph("Offline. tiny.en model. ~500ms on modern CPU. Secondary to keyboard.", s_table_cell)],
        [Paragraph("Command palette", s_table_cell_bold),
         Paragraph("cmdk (Radix)", s_table_cell_bold),
         Paragraph("Ctrl+K. Bridges simple users and power users. Accessible.", s_table_cell)],
    ]
    story.append(make_table(
        ["Layer", "Choice", "Why"],
        stack_data,
        col_widths=[pw * 0.15, pw * 0.2, pw * 0.65],
    ))

    story.append(hr())

    # ── What's Dead ──────────────────────────────────────────────────────
    story.append(Paragraph("4. What We Ruled Out", s_section))

    dead_data = [
        [Paragraph("Tauri", s_table_cell_bold),
         Paragraph("NVDA screen reader regression. Issue #12901. Unresolved.", s_table_cell)],
        [Paragraph("pywebview", s_table_cell_bold),
         Paragraph("NVDA cannot navigate it at all. Issue #545.", s_table_cell)],
        [Paragraph("PyQt6", s_table_cell_bold),
         Paragraph("Screen reader bugs at the Qt framework level. Not fixable.", s_table_cell)],
        [Paragraph("Porcupine", s_table_cell_bold),
         Paragraph("Free tier: 3 users. Then $6,000/year. Use openWakeWord.", s_table_cell)],
        [Paragraph("Voice-first", s_table_cell_bold),
         Paragraph("50-80% failure rate for dysarthric speech. Voice is secondary.", s_table_cell)],
    ]
    story.append(make_table(
        ["Option", "Why it's dead"],
        dead_data,
        col_widths=[pw * 0.2, pw * 0.8],
    ))

    story.append(PageBreak())

    # ── Page 4: The Three Plays ──────────────────────────────────────────
    story.append(Paragraph("5. The Three Innovation Plays", s_section))
    story.append(Paragraph(
        "Build in this order. Each ships independently and delivers value before the next begins.",
        s_body,
    ))

    # Play 1
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Play 1: MCP Server (Week 1)", s_subsection))
    story.append(Paragraph(
        "Expose WindowsAgent as an MCP server. Every existing MCP Windows server "
        "is a dumb pyautogui wrapper. WindowsAgent would be the first with "
        "UIA grounding, app profiles, and verification.",
        s_body,
    ))
    story.append(Paragraph(
        "Claude Desktop, Cursor, and every MCP-compatible AI tool becomes a distribution channel. "
        "No marketing budget needed. Developers find it and tell others.",
        s_body,
    ))

    # Play 2
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Play 2: Floating Voice Pill (Weeks 2-4)", s_subsection))
    story.append(Paragraph(
        "A 48px translucent always-on-top circle. Tap to speak. Visual feedback "
        "during processing. No window chrome. Sits in the corner with personality.",
        s_body,
    ))
    story.append(Paragraph(
        "OpenAI builds this as hardware (Jony Ive device, H2 2026). "
        "Nobody has done it as software on Windows. "
        "This is the demo that makes people share videos.",
        s_body_bold,
    ))
    story.append(Paragraph(
        "Must have a keyboard shortcut equivalent (Ctrl+Space). "
        "Voice fails too often for motor-impaired users to rely on alone.",
        s_warning,
    ))

    # Play 3
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Play 3: UIA Element Overlay (Weeks 5-6)", s_subsection))
    story.append(Paragraph(
        "Chrome DevTools inspect mode for ANY Windows app. Draw colour-coded "
        "bounding boxes over UIA elements. Click to inspect. Drag to build profiles.",
        s_body,
    ))
    story.append(Paragraph(
        "The killer developer feature. Makes profile authoring visual. "
        "Powers demos and marketing. Shows exactly what the agent sees.",
        s_body,
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Then build the full Electron GUI (weeks 7-11) that ties everything together.",
        s_body,
    ))

    story.append(PageBreak())

    # ── Page 5: The Decision ─────────────────────────────────────────────
    story.append(Paragraph("6. Your Decision", s_section))

    # Option A
    story.append(Paragraph("Option A: Innovation Stack (Recommended)", s_subsection))
    story.append(Paragraph(
        "MCP first (1 wk) + Voice Pill (2-3 wk) + Overlay (1-2 wk) + Electron GUI (4-5 wk). "
        "Total: 8-11 weeks.",
        s_body,
    ))

    opt_a = [
        [Paragraph("Competitive advantage", s_table_cell),
         Paragraph("9/10", s_score)],
        [Paragraph("Innovation", s_table_cell),
         Paragraph("9/10", s_score)],
        [Paragraph("Feasibility", s_table_cell),
         Paragraph("7/10", s_score_mid)],
        [Paragraph("Time-to-value", s_table_cell),
         Paragraph("8/10", s_score)],
    ]
    story.append(make_table(["Criterion", "Score"], opt_a, [pw * 0.7, pw * 0.3]))

    story.append(Spacer(1, 6 * mm))

    # Option B
    story.append(Paragraph("Option B: Proven Edge Only", s_subsection))
    story.append(Paragraph(
        "Standard Electron GUI with command palette and voice. Skip MCP, Pill, Overlay. "
        "Total: 8-11 weeks.",
        s_body,
    ))

    opt_b = [
        [Paragraph("Competitive advantage", s_table_cell),
         Paragraph("5/10", s_score_mid)],
        [Paragraph("Innovation", s_table_cell),
         Paragraph("3/10", s_score_low)],
        [Paragraph("Feasibility", s_table_cell),
         Paragraph("9/10", s_score)],
        [Paragraph("Time-to-value", s_table_cell),
         Paragraph("6/10", s_score_mid)],
    ]
    story.append(make_table(["Criterion", "Score"], opt_b, [pw * 0.7, pw * 0.3]))

    story.append(Spacer(1, 6 * mm))

    # Option C
    story.append(Paragraph("Option C: MCP-First, GUI Later", s_subsection))
    story.append(Paragraph(
        "Ship MCP server in week 1. Gather developer feedback. Build GUI based on real needs. "
        "Total: 1 week to first release.",
        s_body,
    ))

    opt_c = [
        [Paragraph("Competitive advantage", s_table_cell),
         Paragraph("7/10", s_score_mid)],
        [Paragraph("Innovation", s_table_cell),
         Paragraph("6/10", s_score_mid)],
        [Paragraph("Feasibility", s_table_cell),
         Paragraph("9/10", s_score)],
        [Paragraph("Time-to-value", s_table_cell),
         Paragraph("10/10", s_score)],
    ]
    story.append(make_table(["Criterion", "Score"], opt_c, [pw * 0.7, pw * 0.3]))

    story.append(hr())

    # Recommendation
    story.append(Paragraph(
        "Recommendation: Option A.",
        ParagraphStyle("Rec", parent=s_callout, fontSize=15, textColor=ACCENT_GREEN),
    ))
    story.append(Paragraph(
        "The build order de-risks it. Each play ships independently. "
        "MCP in week 1 gives developer traction. "
        "The Voice Pill gives the demo video. "
        "The Overlay gives contributors tooling. "
        "The GUI ties it together.",
        s_body,
    ))
    story.append(Paragraph(
        "Option B builds a product nobody talks about. "
        "Option C is smart but leaves the consumer opportunity on the table.",
        s_body,
    ))

    story.append(PageBreak())

    # ── Page 6: Business ─────────────────────────────────────────────────
    story.append(Paragraph("7. Business Model + Funding", s_section))

    pricing_data = [
        [Paragraph("Core", s_table_cell_bold),
         Paragraph("Free / open source", s_table_cell),
         Paragraph("MCP server, CLI, Python library, community profiles", s_table_cell)],
        [Paragraph("Personal", s_table_cell_bold),
         Paragraph("9/month", s_table_cell_bold),
         Paragraph("GUI, voice input, 3 app profiles, community access", s_table_cell)],
        [Paragraph("Professional", s_table_cell_bold),
         Paragraph("29/month", s_table_cell_bold),
         Paragraph("Unlimited profiles, UIA overlay, recording/replay, priority support", s_table_cell)],
        [Paragraph("Enterprise", s_table_cell_bold),
         Paragraph("Custom", s_table_cell),
         Paragraph("On-premise, SSO, audit logging, custom profiles", s_table_cell)],
    ]
    story.append(make_table(
        ["Tier", "Price", "Includes"],
        pricing_data,
        col_widths=[pw * 0.15, pw * 0.2, pw * 0.65],
    ))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("UK Funding Opportunities", s_subsection))

    funding_data = [
        [Paragraph("Access to Work", s_table_cell_bold),
         Paragraph("Up to 66,000/year per disabled employee for AT", s_table_cell)],
        [Paragraph("Innovate UK Smart Grants", s_table_cell_bold),
         Paragraph("Up to 500,000 for innovation projects", s_table_cell)],
        [Paragraph("Digital Inclusion Fund", s_table_cell_bold),
         Paragraph("7.2M pot for 2025/26 (Category 2: innovative interventions)", s_table_cell)],
        [Paragraph("SBRI", s_table_cell_bold),
         Paragraph("Public sector contracts — NHS and DWP commission AT projects", s_table_cell)],
    ]
    story.append(make_table(
        ["Source", "Amount / Details"],
        funding_data,
        col_widths=[pw * 0.3, pw * 0.7],
    ))

    story.append(hr())

    # ── Risk of Inaction ─────────────────────────────────────────────────
    story.append(Paragraph("8. Risk of Inaction", s_section))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> Microsoft ships UFO3 with a consumer GUI. They have UIA expertise, distribution, and budget.",
        s_bullet,
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> The MCP ecosystem matures without a smart Windows bridge. Dumb pyautogui wrappers become 'good enough'.",
        s_bullet,
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> OpenAI ships the Jony Ive voice device and defines the form factor before WindowsAgent exists.",
        s_bullet,
    ))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> The community profile system never reaches critical mass without visual tooling.",
        s_bullet,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Doing nothing is the highest-risk option.",
        s_warning,
    ))

    story.append(hr())

    # ── Positioning ──────────────────────────────────────────────────────
    story.append(Paragraph("9. Positioning", s_section))
    story.append(Paragraph(
        "Do not call it an accessibility tool until disabled users confirm it works for them. "
        "Let accessibility be earned through evidence, not claimed through marketing.",
        s_warning,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Position it as:",
        s_body,
    ))
    story.append(Paragraph(
        '"Desktop automation with keyboard and voice options. '
        'The semantic bridge between AI agents and Windows applications."',
        s_callout,
    ))

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        '"Reads the UI by name, not by pixel."',
        s_pitch,
    ))

    # ── Build ────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=bg_canvas, onLaterPages=bg_canvas)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    build_pdf("docs/WindowsAgent-GUI-Voice-Brief.pdf")
