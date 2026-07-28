"""
MCQCheckboxWidget
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Draws rectangles around detected checkboxes, overlaid on the scan.
  3. Lets the user click a checkbox to toggle its checked / unchecked state,
     redrawing it (color + checkmark) live.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal, QPoint, Qt, QRect
from PyQt6.QtGui import QColor, QPen, QPainter
from PyQt6.QtWidgets import QWidget

from ptyx_mcq.scan.data.documents import Page

from ptyx_mcq.scan.data.conflict_gestion.data_check.cb_styles import CbxColors, CbxThickness
from ptyx_mcq.scan.data.questions import CbxState, Answer

from ptyx_mcq_corrector.review.generic_reviewer import PixReviewer


class Checkbox:
    def __init__(self, answer: Answer, page: Page):
        self.answer = answer
        self.page = page

    @property
    def state(self) -> CbxState | None:
        return self.answer.state

    def __contains__(self, pos: QPoint) -> bool:
        """Test if the given point is inside the checkbox rectangle of the given answer."""
        x, y = pos.x(), pos.y()
        y0, x0 = self.answer.position
        size = self.page.pic.calibration_data.cell_size
        return x0 <= x <= x0 + size and y0 <= y <= y0 + size

    def rect(self) -> QRect:
        """Return the rectangle of the checkbox rectangle of the given answer."""
        y0, x0 = self.answer.position
        size = self.page.pic.calibration_data.cell_size
        return QRect(x0, y0, size, size)

    @property
    def is_checked(self) -> bool:
        checked = self.answer.checked
        assert checked is not None
        return checked

    def toggle(self) -> None:
        self.answer.toggle_state()


# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


class CheckboxesReviewer(PixReviewer):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    checkbox_toggled = pyqtSignal(Checkbox, bool, name="checkbox_toggled")  # (checkbox, new_checked_state)

    _hover: Checkbox | None
    _checkboxes: list[Checkbox]

    CHECKBOX_HOVER_TRANSPARENCY: int = 120

    assert 0 <= CHECKBOX_HOVER_TRANSPARENCY <= 255

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.reset()

    def reset(self) -> None:
        super().reset()
        self._hover = None
        self._checkboxes = []

    # ---- public API ----------------------------------------------------

    def _on_page_set(self) -> None:
        if (page := self.page) is not None:
            self._checkboxes = [Checkbox(answer, page) for question in page.pic for answer in question]

    # ---- Qt events -------------------------------------------------------

    def _on_paint(self, painter: QPainter) -> None:
        """Display the checkboxes, with a different style for each state."""
        for cb in self._checkboxes:
            state = cb.state
            assert state is not None
            wrect = self._image_rect_to_widget(cb.rect())
            color_panel = CbxColors.reviewed_colors if cb.answer.reviewed else CbxColors.default_colors
            color: QColor = QColor(*color_panel[state])
            thickness_panel = (
                CbxThickness.reviewed_thicknesses if cb.answer.reviewed else CbxThickness.default_thicknesses
            )
            thickness: int = thickness_panel[state]
            hover_color = QColor(
                color.red(), color.green(), color.blue(), alpha=self.CHECKBOX_HOVER_TRANSPARENCY
            )
            # noinspection PyTypeChecker
            painter.setBrush(hover_color if cb is self._hover else Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, thickness))
            painter.drawRect(wrect)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            img_pt = self._widget_to_image(event.pos())
            if img_pt is None:
                return
            for cb in self._checkboxes:
                if img_pt in cb:
                    cb.toggle()
                    self.checkbox_toggled.emit(cb, cb.is_checked)
                    self.update()
                    break

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if not self._drag.is_started:
            # Calculate whether the mouse arrow is hovering a checkbox.
            img_pt = self._widget_to_image(event.pos())
            new_hover = None
            if img_pt is not None:
                for cb in self._checkboxes:
                    if img_pt in cb:
                        new_hover = cb
                        break
            if new_hover != self._hover:
                self._hover = new_hover
                self.setCursor(Qt.CursorShape.PointingHandCursor if new_hover else Qt.CursorShape.ArrowCursor)
                self.update()
