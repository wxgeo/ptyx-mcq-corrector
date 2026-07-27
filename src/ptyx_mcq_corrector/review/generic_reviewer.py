"""
PixReviewer
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Lets the user navigate inside (zoom, shift...)
"""

from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import pyqtSignal, QPoint, Qt, QRect
from PyQt6.QtGui import QColor, QPixmap, QPainter, QImage, QWheelEvent, QPen
from PyQt6.QtWidgets import QWidget, QStyleOptionFocusRect

from ptyx_mcq.scan.data.documents import Page


class Zoom:
    MIN = 0.2
    MAX = 8.0
    STEP = 1.15  # multiplicative factor per wheel notch
    FULL_WIDTH = True
    OVERLAPPING_PIXELS = 50  # in pixels: the overlap when scrolling using keyboard.
    OVERLAPPING_RATIO = 0.2  # the overlapping ratio (between 0 and 1) when scrolling using keyboard.


@dataclass
class Transformation:
    zoom: float = 1.0
    shift: QPoint = field(default_factory=lambda: QPoint(0, 0))  # QPoint is mutable!


@dataclass
class Drag:
    parent: "PixReviewer"
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


class PixReviewer(QWidget):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    next_page_requested = pyqtSignal(name="next_page_requested")
    previous_page_requested = pyqtSignal(name="previous_page_requested")
    esc_requested = pyqtSignal(name="esc_requested")

    _cached_pixmap: QPixmap | None
    _page: Page | None
    # The transformation applied by the user, using the mouse wheel and right-button dragging.
    _user_transform: Transformation
    # The global transformation, resulting of both the base transformation automatically calculated for the pixmap
    # to fit the window, and the user defined transformation.
    _transform: Transformation
    _drag: Drag

    BACKGROUND_COLOR: QColor = QColor(245, 245, 245)
    FOCUS_RECT_COLOR: QColor = QColor("cornflowerblue")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.reset()

    def reset(self) -> None:
        self._cached_pixmap = None
        self._page = None
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

    # ---- public API ---------------------------------------------------
    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, page: Page) -> None:
        self.reset()
        self._page = page
        self._on_page_set()
        self.recompute_and_update()

    def _on_page_set(self) -> None:
        """To subclass, to add actions when a new page is set."""

    def validate(self) -> None:
        """To subclass, to implement page validation."""

    # ---- coordinate mapping (widget <-> original image) -----------------

    def _min_vertical_offset(self) -> int:
        """
        The negative minimal value for the vertical offset, so that the bottom of the pixmap reaches the bottom of
        the view.
        """
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

    def _on_paint(self, painter: QPainter) -> None:
        """To subclass, to customize the actions on paint event."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.BACKGROUND_COLOR)

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

        if self.hasFocus():
            option = QStyleOptionFocusRect()
            option.initFrom(self)
            option.rect = self.rect().adjusted(1, 1, -1, -1)
            painter.setPen(QPen(self.FOCUS_RECT_COLOR, 1))
            painter.drawRect(option.rect)

        self._on_paint(painter)

    def mousePressEvent(self, event):
        self.setFocus()
        # right-click drag to pan, left stays for specific actions (like checking checkboxes)
        if event.button() == Qt.MouseButton.RightButton:
            self._drag.start(start_pos=event.pos(), original_shift=self._user_transform.shift)

    def mouseReleaseEvent(self, event):
        self._drag.end()

    def mouseMoveEvent(self, event):
        # Handle drag to move the picture.
        if self._drag.is_started:
            delta = event.pos() - self._drag.start_pos
            self._user_transform.shift = self._drag.original_shift + delta
            self.recompute_and_update()

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
        delta = QPoint(
            0,
            round(max(self.height() - Zoom.OVERLAPPING_PIXELS, (1 - Zoom.OVERLAPPING_RATIO) * self.height())),
        )
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
            case Qt.Key.Key_Escape:
                self.esc_requested.emit()
            case Qt.Key.Key_Space:
                self.reset_zoom()
            case _:
                super().keyPressEvent(event)
