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

from windowsagent.overlay.renderer import (
    colour_for_control_type,
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
        self.update()

    def paintEvent(self, event: Any) -> None:
        """Draw bounding boxes over all visible UIA elements."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dpi = self.overlay.dpi_scale
        query = self.overlay.search_query.lower()

        for elem in self.overlay.elements:
            raw = elem.get("rect", [0, 0, 0, 0])
            left, top, right, bottom = scale_rect(tuple(raw), dpi)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                continue

            ct = elem.get("control_type", "")
            r, g, b, a = colour_for_control_type(ct)

            if query:
                nm = elem.get("name", "").lower()
                aid = elem.get("automation_id", "").lower()
                match = query in nm or query in aid or query in ct.lower()
                a = 100 if match else 15

            is_sel = (
                self.overlay.selected_element is not None
                and elem.get("name") == self.overlay.selected_element.get("name")
                and elem.get("rect") == self.overlay.selected_element.get("rect")
            )
            if is_sel:
                a = 120
                painter.setPen(QPen(QColor(255, 255, 0), 3))
            else:
                painter.setPen(QPen(QColor(r, g, b, min(a + 80, 255)), 1))

            painter.setBrush(QBrush(QColor(r, g, b, a)))
            painter.drawRect(QRect(left, top, w, h))

            if is_sel or (query and a > 15):
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
