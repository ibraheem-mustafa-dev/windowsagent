# Colour Scheme Refactor + Active Element Highlight

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-control-type colour map with 5 functional groups using IBM CVD-safe palette, add 3 presets (Default, High Contrast, Monochrome), switch from fills to borders, and add an active element highlight system using brand orange #FC7908.

**Architecture:** A `ColourScheme` dataclass holds RGBA tuples for 5 functional groups + special states (selected, dimmed, active). A separate `CONTROL_TYPE_GROUPS` dict maps UIA control types to groups. Three preset factories create pre-configured schemes. The widget draws borders (not fills) with pen style differentiation per group (solid/dash/dot). An `active_element_id` field on `OverlayWindow` highlights the element the agent is acting on. The HTTP API and SSE events can update this ID.

**Tech Stack:** Python 3.12, PyQt6 (QPen, Qt.PenStyle), dataclasses, existing FastAPI server

**Key design decisions:**
- IBM CVD-safe palette: Interactive #648FFF (blue), Text Input #FFB000 (amber), Container #785EF0 (purple), Navigation #DC267F (magenta), Other #9AA0A6 (grey)
- Border style differentiation as secondary channel: Interactive=solid, Text Input=dash, Container=dot, Navigation=dash-dot, Other=solid thin
- Brand orange #FC7908 with 4px border for active element
- Selected element: brand teal #118795 with 3px border
- Dimmed alpha: 40 (was 15) for search non-matches
- Borders only, no fills -- fills obscure the app underneath
- `colour_for_control_type()` becomes `colour_for_element()` returning group info + colours
- Backward compatible: old `colour_for_control_type()` still works but delegates to new system

---

## File Structure

```
windowsagent/
  overlay/
    renderer.py        -- MODIFY: Replace _COLOUR_MAP with ColourScheme, CONTROL_TYPE_GROUPS, presets
    widget.py          -- MODIFY: Use borders not fills, pen styles, active element highlight
    __init__.py        -- MODIFY: Export new types
tests/
  test_overlay.py      -- MODIFY: Replace old colour tests, add new scheme/preset/active tests
windowsagent/
  server.py / routes/  -- MODIFY: Add active_element_id endpoint (optional, Task 2)
```

---

## Task 1: ColourScheme Dataclass and Functional Groups

**Files:**
- Modify: `windowsagent/overlay/renderer.py`
- Modify: `tests/test_overlay.py`

### Step 1: Write failing tests for ColourScheme and group mapping

- [ ] **Step 1a: Replace TestColourMapping tests with new scheme tests**

Replace the 5 tests in `TestColourMapping` with tests for the new system. Add new test class `TestColourScheme`:

```python
class TestColourScheme:
    def test_default_scheme_has_five_groups(self) -> None:
        from windowsagent.overlay.renderer import default_scheme
        scheme = default_scheme()
        assert hasattr(scheme, "interactive")
        assert hasattr(scheme, "text_input")
        assert hasattr(scheme, "container")
        assert hasattr(scheme, "navigation")
        assert hasattr(scheme, "other")

    def test_default_scheme_interactive_is_ibm_blue(self) -> None:
        from windowsagent.overlay.renderer import default_scheme
        scheme = default_scheme()
        assert scheme.interactive == (100, 143, 255, 200)  # #648FFF

    def test_default_scheme_active_is_brand_orange(self) -> None:
        from windowsagent.overlay.renderer import default_scheme
        scheme = default_scheme()
        assert scheme.active == (252, 121, 8, 255)  # #FC7908

    def test_default_scheme_selected_is_brand_teal(self) -> None:
        from windowsagent.overlay.renderer import default_scheme
        scheme = default_scheme()
        assert scheme.selected == (17, 135, 149, 255)  # #118795

    def test_high_contrast_scheme_interactive_is_white(self) -> None:
        from windowsagent.overlay.renderer import high_contrast_scheme
        scheme = high_contrast_scheme()
        assert scheme.interactive == (255, 255, 255, 255)

    def test_monochrome_scheme_all_groups_same(self) -> None:
        from windowsagent.overlay.renderer import monochrome_scheme
        scheme = monochrome_scheme()
        assert scheme.interactive == scheme.text_input == scheme.container


class TestControlTypeGroups:
    def test_button_is_interactive(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("Button") == "interactive"

    def test_edit_is_text_input(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("Edit") == "text_input"

    def test_list_is_container(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("List") == "container"

    def test_menu_is_navigation(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("Menu") == "navigation"

    def test_unknown_is_other(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("SomeCustomControl") == "other"

    def test_combobox_is_interactive(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("ComboBox") == "interactive"

    def test_document_is_text_input(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("Document") == "text_input"

    def test_tab_is_navigation(self) -> None:
        from windowsagent.overlay.renderer import group_for_control_type
        assert group_for_control_type("Tab") == "navigation"


class TestColourForElement:
    def test_returns_group_colour(self) -> None:
        from windowsagent.overlay.renderer import colour_for_element, default_scheme
        scheme = default_scheme()
        colour, group, pen_style = colour_for_element("Button", scheme)
        assert colour == scheme.interactive
        assert group == "interactive"

    def test_pen_style_interactive_is_solid(self) -> None:
        from windowsagent.overlay.renderer import colour_for_element, default_scheme, PEN_STYLE_SOLID
        scheme = default_scheme()
        _colour, _group, pen_style = colour_for_element("Button", scheme)
        assert pen_style == PEN_STYLE_SOLID

    def test_pen_style_text_input_is_dash(self) -> None:
        from windowsagent.overlay.renderer import colour_for_element, default_scheme, PEN_STYLE_DASH
        scheme = default_scheme()
        _colour, _group, pen_style = colour_for_element("Edit", scheme)
        assert pen_style == PEN_STYLE_DASH

    def test_pen_style_container_is_dot(self) -> None:
        from windowsagent.overlay.renderer import colour_for_element, default_scheme, PEN_STYLE_DOT
        scheme = default_scheme()
        _colour, _group, pen_style = colour_for_element("List", scheme)
        assert pen_style == PEN_STYLE_DOT

    def test_pen_style_navigation_is_dash_dot(self) -> None:
        from windowsagent.overlay.renderer import colour_for_element, default_scheme, PEN_STYLE_DASH_DOT
        scheme = default_scheme()
        _colour, _group, pen_style = colour_for_element("Menu", scheme)
        assert pen_style == PEN_STYLE_DASH_DOT

    def test_backward_compat_colour_for_control_type(self) -> None:
        from windowsagent.overlay.renderer import colour_for_control_type
        r, g, b, a = colour_for_control_type("Button")
        assert isinstance(r, int)
        assert isinstance(a, int)
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestColourScheme tests/test_overlay.py::TestControlTypeGroups tests/test_overlay.py::TestColourForElement -v`
Expected: FAIL (import errors -- names don't exist yet)

### Step 2: Implement ColourScheme, group mapping, and presets

- [ ] **Step 2a: Replace _COLOUR_MAP in renderer.py with new system**

Replace the `_COLOUR_MAP`, `_DEFAULT_COLOUR`, and `colour_for_control_type` in `renderer.py` with:

```python
from dataclasses import dataclass

# Pen style constants (Qt.PenStyle enum values for pure-function testing without PyQt6)
PEN_STYLE_SOLID = 1      # Qt.PenStyle.SolidLine
PEN_STYLE_DASH = 2       # Qt.PenStyle.DashLine
PEN_STYLE_DOT = 3        # Qt.PenStyle.DotLine
PEN_STYLE_DASH_DOT = 4   # Qt.PenStyle.DashDotLine


@dataclass(frozen=True)
class ColourScheme:
    """Colour scheme for overlay bounding boxes.

    Each field is an (R, G, B, A) tuple. The 5 functional groups cover
    all UIA control types. Special states override group colours.
    """
    interactive: tuple[int, int, int, int]   # Buttons, checkboxes, sliders, combos
    text_input: tuple[int, int, int, int]    # Edit, Document, ComboBox (editable)
    container: tuple[int, int, int, int]     # List, Tree, DataGrid, Table, Group
    navigation: tuple[int, int, int, int]    # Menu, MenuBar, Tab, TabItem, Hyperlink
    other: tuple[int, int, int, int]         # Pane, Window, Text, Image, etc.
    selected: tuple[int, int, int, int]      # User-clicked element
    dimmed: tuple[int, int, int, int]        # Non-matching during search
    active: tuple[int, int, int, int]        # Agent is acting on this element


def default_scheme() -> ColourScheme:
    """IBM CVD-safe palette -- default preset."""
    return ColourScheme(
        interactive=(100, 143, 255, 200),    # #648FFF blue
        text_input=(255, 176, 0, 200),       # #FFB000 amber
        container=(120, 94, 240, 200),       # #785EF0 purple
        navigation=(220, 38, 127, 200),      # #DC267F magenta
        other=(154, 160, 166, 200),          # #9AA0A6 grey
        selected=(17, 135, 149, 255),        # #118795 brand teal
        dimmed=(154, 160, 166, 40),          # grey, low alpha
        active=(252, 121, 8, 255),           # #FC7908 brand orange
    )


def high_contrast_scheme() -> ColourScheme:
    """High contrast preset for maximum visibility."""
    return ColourScheme(
        interactive=(255, 255, 255, 255),    # white
        text_input=(255, 255, 0, 255),       # yellow
        container=(0, 255, 255, 255),        # cyan
        navigation=(255, 0, 255, 255),       # magenta
        other=(192, 192, 192, 255),          # silver
        selected=(0, 255, 0, 255),           # green
        dimmed=(80, 80, 80, 100),            # dark grey
        active=(255, 165, 0, 255),           # orange
    )


def monochrome_scheme() -> ColourScheme:
    """Single-colour preset -- differentiation by pen style only."""
    mono = (200, 200, 200, 180)
    return ColourScheme(
        interactive=mono,
        text_input=mono,
        container=mono,
        navigation=mono,
        other=mono,
        selected=(255, 255, 255, 255),
        dimmed=(100, 100, 100, 60),
        active=(252, 121, 8, 255),           # brand orange still distinct
    )


# Map UIA control types to functional groups
CONTROL_TYPE_GROUPS: dict[str, str] = {
    # Interactive
    "Button": "interactive",
    "SplitButton": "interactive",
    "CheckBox": "interactive",
    "RadioButton": "interactive",
    "ComboBox": "interactive",
    "Slider": "interactive",
    "Spinner": "interactive",
    "ScrollBar": "interactive",
    "Thumb": "interactive",
    # Text Input
    "Edit": "text_input",
    "Document": "text_input",
    # Container
    "List": "container",
    "ListItem": "container",
    "DataGrid": "container",
    "DataItem": "container",
    "Tree": "container",
    "TreeItem": "container",
    "Table": "container",
    "Group": "container",
    # Navigation
    "Menu": "navigation",
    "MenuBar": "navigation",
    "MenuItem": "navigation",
    "Tab": "navigation",
    "TabItem": "navigation",
    "Hyperlink": "navigation",
    "ToolBar": "navigation",
}

# Pen styles per group (secondary channel for CVD users)
_GROUP_PEN_STYLES: dict[str, int] = {
    "interactive": PEN_STYLE_SOLID,
    "text_input": PEN_STYLE_DASH,
    "container": PEN_STYLE_DOT,
    "navigation": PEN_STYLE_DASH_DOT,
    "other": PEN_STYLE_SOLID,
}


def group_for_control_type(control_type: str) -> str:
    """Return the functional group name for a UIA control type."""
    return CONTROL_TYPE_GROUPS.get(control_type, "other")


def colour_for_element(
    control_type: str,
    scheme: ColourScheme,
) -> tuple[tuple[int, int, int, int], str, int]:
    """Return (colour, group_name, pen_style) for a control type and scheme.

    Args:
        control_type: UIA control type string.
        scheme: ColourScheme to use.

    Returns:
        Tuple of (RGBA colour, group name, pen style constant).
    """
    group = group_for_control_type(control_type)
    colour: tuple[int, int, int, int] = getattr(scheme, group)
    pen_style = _GROUP_PEN_STYLES.get(group, PEN_STYLE_SOLID)
    return colour, group, pen_style


def colour_for_control_type(control_type: str) -> tuple[int, int, int, int]:
    """Backward-compatible: return (R, G, B, A) for a control type.

    Uses the default CVD-safe scheme.
    """
    colour, _group, _pen = colour_for_element(control_type, default_scheme())
    return colour
```

- [ ] **Step 2b: Run new tests to verify they pass**

Run: `python -m pytest tests/test_overlay.py::TestColourScheme tests/test_overlay.py::TestControlTypeGroups tests/test_overlay.py::TestColourForElement -v`
Expected: PASS

- [ ] **Step 2c: Run full test suite to check backward compatibility**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 289+ tests pass (old TestColourMapping tests removed, new ones added)

- [ ] **Step 2d: Run mypy**

Run: `python -m mypy windowsagent/overlay/renderer.py`
Expected: 0 errors

- [ ] **Step 2e: Commit**

```bash
git add windowsagent/overlay/renderer.py tests/test_overlay.py
git commit -m "feat(overlay): ColourScheme dataclass with 5 functional groups, 3 CVD-safe presets"
```

---

## Task 2: Refactor Widget to Use Borders (Not Fills) and Pen Styles

**Files:**
- Modify: `windowsagent/overlay/widget.py`
- Modify: `windowsagent/overlay/__init__.py`

### Step 3: Update widget.py to draw borders with pen style differentiation

- [ ] **Step 3a: Refactor paintEvent in widget.py**

Replace the `paintEvent` method to:
1. Use `QPen` with width 2 and `Qt.PenStyle` matching the group
2. Use `QBrush(Qt.BrushStyle.NoBrush)` instead of filled brush
3. Use scheme from `self.overlay.scheme`
4. Draw active element with brand orange 4px border
5. Draw selected element with brand teal 3px border

The key changes in `widget.py`:
- Import `colour_for_element`, `default_scheme`, `ColourScheme` and pen style constants
- Map `PEN_STYLE_*` constants to `Qt.PenStyle` enum values
- Replace `painter.setBrush(QBrush(QColor(...)))` with `painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))`
- Add active element check before selected element check

- [ ] **Step 3b: Add `scheme` and `active_element_id` fields to OverlayWindow**

In `renderer.py`, update `OverlayWindow.__init__` to add:
```python
self.scheme: ColourScheme = default_scheme()
self.active_element_id: str | None = None
```

- [ ] **Step 3c: Update __init__.py exports**

Add `ColourScheme`, `default_scheme`, `high_contrast_scheme`, `monochrome_scheme`, `group_for_control_type`, `colour_for_element` to `__all__`.

- [ ] **Step 3d: Run full test suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 289+ tests pass

- [ ] **Step 3e: Run mypy**

Run: `python -m mypy windowsagent/overlay/`
Expected: 0 errors

- [ ] **Step 3f: Commit**

```bash
git add windowsagent/overlay/
git commit -m "feat(overlay): borders not fills, pen style differentiation per functional group"
```

---

## Task 3: Active Element Highlight System

**Files:**
- Modify: `windowsagent/overlay/renderer.py`
- Modify: `windowsagent/overlay/widget.py`
- Modify: `windowsagent/routes/agent.py` (SSE event for active element)
- Modify: `tests/test_overlay.py`

### Step 4: Write failing tests for active element

- [ ] **Step 4a: Add active element tests**

```python
class TestActiveElement:
    def test_overlay_window_has_active_element_id(self) -> None:
        """OverlayWindow must have an active_element_id field."""
        from windowsagent.overlay.renderer import OverlayWindow
        # OverlayWindow requires PyQt6 -- test the field exists on the class
        import inspect
        sig = inspect.signature(OverlayWindow.__init__)
        # Just verify the attribute is set in __init__ by checking source
        source = inspect.getsource(OverlayWindow.__init__)
        assert "active_element_id" in source

    def test_active_colour_is_brand_orange(self) -> None:
        from windowsagent.overlay.renderer import default_scheme
        scheme = default_scheme()
        assert scheme.active == (252, 121, 8, 255)

    def test_active_border_width_constant(self) -> None:
        from windowsagent.overlay.renderer import ACTIVE_BORDER_WIDTH
        assert ACTIVE_BORDER_WIDTH == 4

    def test_selected_border_width_constant(self) -> None:
        from windowsagent.overlay.renderer import SELECTED_BORDER_WIDTH
        assert SELECTED_BORDER_WIDTH == 3

    def test_default_border_width_constant(self) -> None:
        from windowsagent.overlay.renderer import DEFAULT_BORDER_WIDTH
        assert DEFAULT_BORDER_WIDTH == 2
```

- [ ] **Step 4b: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay.py::TestActiveElement -v`
Expected: FAIL

### Step 5: Implement active element constants and widget logic

- [ ] **Step 5a: Add border width constants to renderer.py**

```python
# Border widths
ACTIVE_BORDER_WIDTH = 4
SELECTED_BORDER_WIDTH = 3
DEFAULT_BORDER_WIDTH = 2
```

- [ ] **Step 5b: Update widget.py paintEvent for active element**

In `paintEvent`, before the selected-element check, add:

```python
is_active = (
    self.overlay.active_element_id is not None
    and elem.get("automation_id") == self.overlay.active_element_id
)
if is_active:
    pen = QPen(QColor(*scheme.active), ACTIVE_BORDER_WIDTH)
    pen.setStyle(Qt.PenStyle.SolidLine)
    painter.setPen(pen)
    painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    painter.drawRect(QRect(left, top, w, h))
    # Draw label
    label = f"ACTIVE: {elem.get('name', '')} [{ct}]"
    painter.setPen(QPen(QColor(255, 255, 255)))
    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    painter.drawText(left + 2, top - 6, label)
    continue
```

- [ ] **Step 5c: Run tests**

Run: `python -m pytest tests/test_overlay.py -v`
Expected: PASS

- [ ] **Step 5d: Run full suite + mypy**

Run: `python -m pytest tests/ -m "not integration" -q && python -m mypy windowsagent/overlay/`
Expected: 289+ pass, 0 mypy errors

- [ ] **Step 5e: Commit**

```bash
git add windowsagent/overlay/ tests/test_overlay.py
git commit -m "feat(overlay): active element highlight with brand orange 4px border"
```

---

## Task 4: SSE Integration for Active Element Updates

**Files:**
- Modify: `windowsagent/overlay/renderer.py`
- Modify: `windowsagent/overlay/widget.py`

### Step 6: Add active element update via HTTP polling

- [ ] **Step 6a: Add fetch_active_element to renderer.py**

```python
def fetch_active_element() -> str | None:
    """Fetch current active element ID from agent server."""
    try:
        resp = httpx.get(f"{BASE_URL}/agent/active-element", timeout=2.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("automation_id")
    except Exception:
        return None
```

- [ ] **Step 6b: Update widget _refresh_elements to poll active element**

In `_refresh_elements`, after fetching UIA tree, add:

```python
self.overlay.active_element_id = fetch_active_element()
```

- [ ] **Step 6c: Run full suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: 289+ pass

- [ ] **Step 6d: Commit**

```bash
git add windowsagent/overlay/
git commit -m "feat(overlay): poll active element ID from agent server"
```

---

## Guardrails

- **Tests:** 289+ unit tests must keep passing after every commit. Run `python -m pytest tests/ -m "not integration" -q`
- **Types:** mypy must stay at 0 errors. Run `python -m mypy windowsagent/`
- **Lint:** ruff 0 new warnings. 2 pre-existing RUF005 in routes/system.py -- ignore.
- **File limits:** Python files under 250 lines. `renderer.py` will grow -- monitor.
- **PyQt6 guard:** All PyQt6 imports behind `try/except ImportError`. Pure functions testable without PyQt6.
- **No fills:** Borders only. `QBrush(Qt.BrushStyle.NoBrush)` everywhere.
- **CVD safety:** IBM palette verified. Pen styles as secondary differentiation channel.
