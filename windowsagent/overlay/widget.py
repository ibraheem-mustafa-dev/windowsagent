"""
PyQt6 overlay widget -- internal Qt rendering implementation.

This module contains the actual QWidget subclass that draws bounding boxes.
Separated from renderer.py to keep files under 250 lines.
"""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from windowsagent.overlay.colours import (
    ACTIVE_BORDER_WIDTH,
    DEFAULT_BORDER_WIDTH,
    PEN_STYLE_DASH,
    PEN_STYLE_DASH_DOT,
    PEN_STYLE_DOT,
    PEN_STYLE_SOLID,
    SELECTED_BORDER_WIDTH,
    colour_for_element,
)
from windowsagent.overlay.renderer import (
    fetch_active_element,
    fetch_uia_tree,
    flatten_elements,
    scale_rect,
)


class OverlayWidget(QWidget):
    """Transparent Qt widget that draws UIA element bounding boxes."""

    def __init__(self, overlay: Any) -> None:
        super().__init__()
        self.overlay = overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_elements)
        self._timer.start(overlay.refresh_ms)
        self._refresh_elements()

    def _refresh_elements(self) -> None:
        """Fetch UIA tree and flatten into drawable elements."""
        tree = fetch_uia_tree(self.overlay.target_window)
        if tree is not None:
            self.overlay.elements = flatten_elements(tree)
        self.overlay.active_element_id = fetch_active_element()
        self.update()

    def _qt_pen_style(self, pen_const: int) -> Qt.PenStyle:
        """Map PEN_STYLE_* constant to Qt.PenStyle enum."""
        return {
            PEN_STYLE_SOLID: Qt.PenStyle.SolidLine,
            PEN_STYLE_DASH: Qt.PenStyle.DashLine,
            PEN_STYLE_DOT: Qt.PenStyle.DotLine,
            PEN_STYLE_DASH_DOT: Qt.PenStyle.DashDotLine,
        }.get(pen_const, Qt.PenStyle.SolidLine)

    def paintEvent(self, event: Any) -> None:
        """Draw border-only bounding boxes over visible UIA elements."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        no_brush = QBrush(Qt.BrushStyle.NoBrush)
        dpi = self.overlay.dpi_scale
        query = self.overlay.search_query.lower()
        scheme = self.overlay.scheme
        active_id = self.overlay.active_element_id

        for elem in self.overlay.elements:
            raw = elem.get("rect", [0, 0, 0, 0])
            left, top, right, bottom = scale_rect(tuple(raw), dpi)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                continue

            ct = elem.get("control_type", "")
            aid = elem.get("automation_id", "")
            r, g, b, a = colour_for_element(ct, scheme)[0]
            _group, pen_style_const = colour_for_element(ct, scheme)[1:]

            # Active element: brand orange thick border
            is_active = active_id is not None and aid == active_id
            if is_active:
                pen = QPen(QColor(*scheme.active), ACTIVE_BORDER_WIDTH)
                pen.setStyle(Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.setBrush(no_brush)
                painter.drawRect(QRect(left, top, w, h))
                label = f"ACTIVE: {elem.get('name', '')} [{ct}]"
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(left + 2, top - 6, label)
                continue

            # Selected element: brand teal
            is_sel = (
                self.overlay.selected_element is not None
                and elem.get("name") == self.overlay.selected_element.get("name")
                and elem.get("rect") == self.overlay.selected_element.get("rect")
            )

            # Search dimming
            if query:
                nm = elem.get("name", "").lower()
                match = query in nm or query in aid.lower() or query in ct.lower()
                if not match:
                    r, g, b, a = scheme.dimmed

            if is_sel:
                pen = QPen(QColor(*scheme.selected), SELECTED_BORDER_WIDTH)
                pen.setStyle(Qt.PenStyle.SolidLine)
            else:
                pen = QPen(QColor(r, g, b, a), DEFAULT_BORDER_WIDTH)
                pen.setStyle(self._qt_pen_style(pen_style_const))

            painter.setPen(pen)
            painter.setBrush(no_brush)
            painter.drawRect(QRect(left, top, w, h))

            if is_sel or (query and a > scheme.dimmed[3]):
                label = f"{elem.get('name', '')} [{ct}]"
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(left + 2, top - 4, label)

        painter.end()

    def mousePressEvent(self, event: Any) -> None:
        """Find the smallest element under the click and select it."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        cx, cy = int(pos.x()), int(pos.y())
        dpi = self.overlay.dpi_scale

        best: dict[str, Any] | None = None
        best_area = float("inf")
        for elem in self.overlay.elements:
            raw = elem.get("rect", [0, 0, 0, 0])
            el, et, er, eb = scale_rect(tuple(raw), dpi)
            if el <= cx <= er and et <= cy <= eb:
                area = (er - el) * (eb - et)
                if area < best_area:
                    best = elem
                    best_area = area

        self.overlay.selected_element = best
        if best and self.overlay._on_element_selected:
            self.overlay._on_element_selected(best)
        self.update()

    def keyPressEvent(self, event: Any) -> None:
        """Handle Escape (close) and F5 (refresh)."""
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_F5:
            self._refresh_elements()
