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

from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import pyqtSignal, QPoint, Qt, QRect
from PyQt6.QtGui import QColor, QPixmap, QPen, QPainter, QImage, QWheelEvent
from PyQt6.QtWidgets import QWidget

from ptyx_mcq.scan.data import Page, Answer

from ptyx_mcq.scan.data.conflict_gestion.data_check.cb_styles import CbxColors, CbxThickness
from ptyx_mcq.scan.data.questions import CbxState


class Zoom:
    MIN = 0.2
    MAX = 8.0
    STEP = 1.15  # multiplicative factor per wheel notch
    FULL_WIDTH = True


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


@dataclass
class Transformation:
    zoom: float = 1.0
    shift: QPoint = field(default_factory=lambda: QPoint(0, 0))  # QPoint is mutable!


@dataclass
class Drag:
    parent: CheckboxesReviewer
    is_started: bool = False
    start_pos: QPoint = field(default_factory=lambda: QPoint(0, 0))  # QPoint is mutable!
    original_shift: QPoint = field(default_factory=lambda: QPoint(0, 0))  # QPoint is mutable!

    def start(self, start_pos: QPoint, original_shift: QPoint) -> None:
        self.is_started = True
        self.start_pos = start_pos
        self.original_shift = original_shift
        self.parent.setCursor(Qt.CursorShape.ClosedHandCursor)

    def end(self) -> None:
        self.is_started = False
        self.parent.setCursor(Qt.CursorShape.ArrowCursor)


# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


class CheckboxesReviewer(QWidget):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    checkbox_toggled = pyqtSignal(Checkbox, bool, name="checkbox_toggled")  # (checkbox, new_checked_state)
    next_page_requested = pyqtSignal(name="next_page_requested")
    previous_page_requested = pyqtSignal(name="previous_page_requested")

    _cached_pixmap: QPixmap | None
    _hover: Checkbox | None
    _page: Page | None
    _checkboxes: list[Checkbox]
    # The transformation applied by the user, using the mouse wheel and right-button dragging.
    _user_transform: Transformation
    # The global transformation, resulting of both the base transformation automatically calculated for the pixmap
    # to fit the window, and the user defined transformation.
    _transform: Transformation
    _drag: Drag

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.reset()

    def reset(self) -> None:
        self._cached_pixmap = None
        self._hover = None
        self._page = None
        self._checkboxes = []
        self._transform = Transformation()
        self._user_transform = Transformation()
        self._drag = Drag(self)

    def reset_zoom(self) -> None:
        self._user_transform = Transformation()
        self.recompute_and_update()

    @property
    def pixmap(self) -> QPixmap | None:
        """Return the pixmap of the MCQ image of the current page, if any, else `None`."""
        if self._page is None:
            self._cached_pixmap = None
        elif self._cached_pixmap is None:
            self._cached_pixmap = QPixmap.fromImage(QImage(str(self._page.pic.path)))
        return self._cached_pixmap

    # def current_checkbox(self) -> Checkbox | None:
    #     """Return the checkbox currently hovered, if any, else `None`."""
    #     for cb in self._checkboxes:
    #         pos = self._widget_to_image(self.mapFromGlobal(QCursor.pos()))
    #         if pos is not None and pos in cb:
    #             return cb
    #     return None

    # ---- public API ----------------------------------------------------

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, page: Page) -> None:
        self.reset()
        self._page = page
        self._checkboxes = [Checkbox(answer, page) for question in page.pic for answer in question]
        self.recompute_and_update()

    def validate(self) -> None:
        """Save the checkboxes' states changes on the drive."""
        if (page := self.page) is not None:
            page.pic.save_checkboxes_state(is_fix=True)

    # @property
    # def checkboxes(self) -> Iterator[Checkbox]:
    #     if (page := self.page) is None:
    #         return iter([])
    #     return iter(Checkbox(answer, page) for question in page.pic for answer in question)

    # ---- coordinate mapping (widget <-> original image) -----------------

    def _min_vertical_offset(self) -> int:
        """The negative"""
        if (pixmap := self.pixmap) is None:
            return 0
        return self.height() - round(pixmap.height() * self._transform.zoom)

    def _recompute_transform(self) -> None:
        if (pixmap := self.pixmap) is None:
            return
        pw, ph = pixmap.width(), pixmap.height()
        if pw == 0 or ph == 0:
            return
        vw, vh = self.width(), self.height()
        # Default scale so that the pixmap fits in the window.
        if Zoom.FULL_WIDTH:
            base_scale = max(vw / pw, vh / ph)
        else:
            base_scale = min(vw / pw, vh / ph)
        self._transform.zoom = zoom = base_scale * self._user_transform.zoom

        disp_w, disp_h = pw * zoom, ph * zoom
        if Zoom.FULL_WIDTH:
            # Default offset so that the pixmap is centered horizontally in the window.
            base_offset = QPoint(int((vw - disp_w) / 2), 0)
        else:
            # Default offset so that the pixmap is centered in the window.
            base_offset = QPoint(int((vw - disp_w) / 2), int((vh - disp_h) / 2))
        # The vertical offset must always be kept negative,
        # since the top of the picture should never go below the top of the screen.
        if (base_offset + self._user_transform.shift).y() > 0:
            self._user_transform.shift.setY(-base_offset.y())
        if (base_offset + self._user_transform.shift).y() < self._min_vertical_offset():
            self._user_transform.shift.setY(self._min_vertical_offset() - base_offset.y())
        self._transform.shift = base_offset + self._user_transform.shift
        print("offset:", self._transform.shift)

    def recompute_and_update(self) -> None:
        self._recompute_transform()
        self.update()

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

        # print(self._hover, len(list(self.checkboxes)))
        for cb in self._checkboxes:
            wrect = self._image_rect_to_widget(cb.rect())
            color_panel = CbxColors.reviewed_colors if cb.answer.reviewed else CbxColors.default_colors
            # noinspection PyTypeChecker
            color: QColor = QColor(*color_panel.get(cb.state, (0, 0, 0)))
            thickness_panel = (
                CbxThickness.reviewed_thicknesses if cb.answer.reviewed else CbxThickness.default_thicknesses
            )
            # noinspection PyTypeChecker
            thickness: int = thickness_panel.get(cb.state, 2)
            # if cb is self._hover:
            #     print("Checkbox hovered.")
            hover_color = QColor(color.red(), color.green(), color.blue(), alpha=60)
            # noinspection PyTypeChecker
            painter.setBrush(hover_color if cb is self._hover else Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, thickness))
            painter.drawRect(wrect)

    def mousePressEvent(self, event):
        self.setFocus()
        if (
            event.button() == Qt.MouseButton.RightButton
        ):  # right-click drag to pan, left stays for toggling checkboxes
            self._drag.start(start_pos=event.pos(), original_shift=self._user_transform.shift)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

        elif event.button() == Qt.MouseButton.LeftButton:
            img_pt = self._widget_to_image(event.pos())
            if img_pt is None:
                return
            for cb in self._checkboxes:
                if img_pt in cb:
                    cb.toggle()
                    self.checkbox_toggled.emit(cb, cb.is_checked)
                    self.update()
                    break

    def mouseReleaseEvent(self, event):
        self._drag.end()

    def mouseMoveEvent(self, event):
        # Handle drag to move the picture.
        if self._drag.is_started:
            delta = event.pos() - self._drag.start_pos
            self._user_transform.shift = self._drag.original_shift + delta
            self.recompute_and_update()
            return
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

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if self.pixmap is None or event is None:
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

    def keyPressEvent(self, event):
        zoom = self._transform.zoom
        if zoom == 0:
            return
        delta = QPoint(0, round(self.height()))
        match event.key():
            case Qt.Key.Key_Down:
                self._user_transform.shift -= delta
                self.recompute_and_update()
            case Qt.Key.Key_Up:
                self._user_transform.shift += delta
                self.recompute_and_update()
            case Qt.Key.Key_Left:
                self.previous_page_requested.emit()
            case Qt.Key.Key_Right:
                self.next_page_requested.emit()
            case Qt.Key.Key_Home:
                self._user_transform.shift.setY(0)
                self.recompute_and_update()
            case Qt.Key.Key_End:
                base_shift = self._transform.shift - self._user_transform.shift
                self._user_transform.shift.setY(self._min_vertical_offset() - base_shift.y())
                self.recompute_and_update()
            case Qt.Key.Key_Escape | Qt.Key.Key_Space:
                self.reset_zoom()
            case _:
                super().keyPressEvent(event)
