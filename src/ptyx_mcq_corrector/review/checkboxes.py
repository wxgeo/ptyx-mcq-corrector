"""
MCQCheckboxWidget
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Draws rectangles around detected checkboxes, overlaid on the scan.
  3. Lets the user click a checkbox to toggle its checked / unchecked state,
     redrawing it (color + checkmark) live.

Dependencies:
    pip install PyQt5 opencv-python-headless numpy

Run this file directly for a self-contained demo (it generates a synthetic
scanned form, auto-detects the checkbox squares with OpenCV, and opens the
widget so you can click boxes to toggle them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Iterator

from PIL.ImageQt import ImageQt
from PyQt6.QtCore import pyqtSignal, QPoint, Qt, QRect
from PyQt6.QtGui import QColor, QPixmap, QPen, QPainter, QCursor, QImage, QWheelEvent
from PyQt6.QtWidgets import QWidget

from ptyx_mcq.scan.data import Page, Answer


class Zoom:
    MIN = 0.2
    MAX = 8.0
    STEP = 1.15  # multiplicative factor per wheel notch


class Checkbox:
    def __init__(self, answer: Answer, page: Page):
        self.answer = answer
        self.page = page

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


@dataclass
class Transformation:
    zoom: float = 1.0
    shift: QPoint = field(default_factory=lambda: QPoint(0, 0))  # QPoint is mutable!


# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


class CheckboxesReviewer(QWidget):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    checkboxToggled = pyqtSignal(Checkbox, bool)  # (checkbox, new_checked_state)

    UNCHECKED_COLOR = QColor(220, 40, 40)  # red outline
    CHECKED_COLOR = QColor(30, 160, 60)  # green outline
    CHECKED_FILL = QColor(30, 160, 60, 60)  # translucent green fill
    HOVER_COLOR = QColor(40, 120, 220)  # blue while hovering

    _cached_pixmap: QPixmap | None
    _hover: Checkbox | None
    _page: Page | None
    # The transformation applied by the user, using the mouse wheel and right-button dragging.
    _user_transform: Transformation
    # The global transformation, resulting of both the base transformation automatically calculated for the pixmap
    # to fit the window, and the user defined transformation.
    _transform: Transformation

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)
        self.reset()

    def reset(self) -> None:
        self._cached_pixmap = None
        self._hover = None
        self._page = None
        self._transform = Transformation()
        self._user_transform = Transformation()

    def reset_zoom(self) -> None:
        self._user_transform = Transformation()
        self._recompute_transform()
        self.update()

    @property
    def pixmap(self) -> QPixmap | None:
        """Return the pixmap of the MCQ image of the current page, if any, else `None`."""
        if self._page is None:
            self._cached_pixmap = None
        elif self._cached_pixmap is None:
            self._cached_pixmap = QPixmap.fromImage(QImage(str(self._page.pic.path)))
        return self._cached_pixmap

    def current_checkbox(self) -> Checkbox | None:
        """Return the checkbox currently hovered, if any, else `None`."""
        for cb in self.checkboxes:
            pos = self._widget_to_image(self.mapFromGlobal(QCursor.pos()))
            if pos is not None and pos in cb:
                return cb
        return None

    # ---- public API ----------------------------------------------------

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, page: Page) -> None:
        self.reset()
        self._page = page
        self._recompute_transform()
        self.update()

    @property
    def checkboxes(self) -> Iterator[Checkbox]:
        if (page := self.page) is None:
            return iter([])
        return iter(Checkbox(answer, page) for question in page.pic for answer in question)

    # ---- coordinate mapping (widget <-> original image) -----------------

    def _recompute_transform(self) -> None:
        if (pixmap := self.pixmap) is None:
            return
        pw, ph = pixmap.width(), pixmap.height()
        if pw == 0 or ph == 0:
            return
        vw, vh = self.width(), self.height()
        # Default scale so that the pixmap fits in the window.
        base_scale = min(vw / pw, vh / ph)
        self._transform.zoom = zoom = base_scale * self._user_transform.zoom

        disp_w, disp_h = pw * zoom, ph * zoom
        # Default offset so that the pixmap is centered in the window.
        base_offset = QPoint(int((vw - disp_w) / 2), int((vh - disp_h) / 2))
        self._transform.shift = base_offset + self._user_transform.shift

    def _widget_to_image(self, pos: QPoint) -> QPoint | None:
        zoom = self._transform.zoom
        shift = self._transform.shift
        if (pixmap := self.pixmap) is None or zoom == 0:
            return None
        x = (pos.x() - shift.x()) / zoom
        y = (pos.y() - shift.y()) / zoom
        if 0 <= x <= pixmap.width() and 0 <= y <= pixmap.height():
            return QPoint(int(x), int(y))
        return None

    def _image_to_widget_point(self, pt: QPoint) -> QPoint:
        zoom = self._transform.zoom
        shift = self._transform.shift
        return QPoint(round(pt.x() * zoom) + shift.x(), round(pt.y() * zoom) + shift.y())

    def _image_rect_to_widget(self, rect: QRect) -> QRect:
        zoom = self._transform.zoom
        shift = self._transform.shift
        return QRect(
            int(rect.x() * zoom) + shift.x(),
            int(rect.y() * zoom) + shift.y(),
            max(1, int(rect.width() * zoom)),
            max(1, int(rect.height() * zoom)),
        )

    # ---- Qt events -------------------------------------------------------

    def resizeEvent(self, event):
        self._recompute_transform()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(245, 245, 245))

        pixmap = self.pixmap
        if pixmap is None:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image loaded")
            return

        self._recompute_transform()
        zoom = self._transform.zoom
        shift = self._transform.shift
        disp_w = pixmap.width() * zoom
        disp_h = pixmap.height() * zoom
        target = QRect(shift.x(), shift.y(), int(disp_w), int(disp_h))
        painter.drawPixmap(target, pixmap)

        for cb in self.checkboxes:
            wrect = self._image_rect_to_widget(cb.rect())

            if cb.is_checked:
                pen = QPen(self.CHECKED_COLOR, 3)
                painter.setPen(pen)
                painter.setBrush(self.CHECKED_FILL)
                painter.drawRect(wrect)
            else:
                color = self.HOVER_COLOR if cb is self._hover else self.UNCHECKED_COLOR
                painter.setPen(QPen(color, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(wrect)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        img_pt = self._widget_to_image(event.pos())
        if img_pt is None:
            return
        for cb in self.checkboxes:
            if img_pt in cb:
                cb.toggle()
                self.checkboxToggled.emit(cb, cb.is_checked)
                self.update()
                break

    def mouseMoveEvent(self, event):
        img_pt = self._widget_to_image(event.pos())
        new_hover = None
        if img_pt is not None:
            for cb in self.checkboxes:
                if img_pt in cb:
                    new_hover = cb
                    break
        if new_hover != self._hover:
            self._hover = new_hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if new_hover else Qt.CursorShape.ArrowCursor)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.pixmap is None:
            return

        # Position in image coordinates BEFORE zoom change, so we can keep it fixed
        old_img_pt = self._widget_to_image(event.position().toPoint())

        angle = event.angleDelta().y()
        if angle > 0:
            self._user_transform.zoom = min(self._user_transform.zoom * Zoom.STEP, Zoom.MAX)
        elif angle < 0:
            self._user_transform.zoom = max(self._user_transform.zoom / Zoom.STEP, Zoom.MIN)
        else:
            return

        self._recompute_transform()

        if old_img_pt is not None:
            # Recompute where that same image point now lands in widget coords,
            # and adjust pan so it stays under the cursor.
            new_widget_pt = self._image_to_widget_point(old_img_pt)
            delta = event.position().toPoint() - new_widget_pt
            self._user_transform.shift += delta
            self._recompute_transform()

        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_zoom()
