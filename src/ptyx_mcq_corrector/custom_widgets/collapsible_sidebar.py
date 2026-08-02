"""
Generic, reusable CollapsibleSidebar widget for PyQt6.

Wrap ANY content widget (a list, a tree, a form, ...) with a title, and you
get a sidebar that:
  - shows a header with the title + a "«" button to slim it down
  - collapses to a thin vertical tab (PyCharm-style) instead of disappearing
  - expands again when that tab is clicked
  - animates the width change

Usage:
    content = QListWidget()
    content.addItems(["Item A", "Item B"])
    sidebar = CollapsibleSidebar("My List", content)
"""

from PyQt6.QtCore import Qt, QRect, QVariantAnimation, QEasingCurve
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QSizePolicy,
    QToolButton,
    QStyleOptionToolButton,
    QStyle,
)


class VerticalTabButton(QToolButton):
    """
    A button that draws its text rotated 90°, used as the thin
    "click to expand" strip when a sidebar is collapsed - similar to
    the vertical tool-window tabs in PyCharm/IntelliJ.
    """

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.rotate(90)
        painter.translate(0, -self.width())

        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        # Swap width/height so the style draws into a "rotated" rect
        opt.rect = QRect(0, 0, opt.rect.height(), opt.rect.width())

        self.style().drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt, painter, self)
        painter.end()

    def sizeHint(self):
        size = super().sizeHint()
        return size.transposed()


class CollapsibleSidebar(QWidget):
    """
    A generic sidebar panel that slims down to a thin vertical tab instead
    of disappearing, and expands again when that tab is clicked.

    Parameters
    ----------
    title : str
        Shown in the expanded header and on the collapsed vertical tab.
    content_widget : QWidget
        Whatever you want inside the sidebar (QListWidget, QTreeWidget,
        a custom form, ...). This class only manages the collapse/expand
        chrome around it.
    expanded_width, collapsed_width : int
        Widths (in px) for the two states.
    animation_ms : int
        Duration of the slide animation.
    """

    def __init__(
        self, title, content_widget, expanded_width=200, collapsed_width=28, animation_ms=180, parent=None
    ):
        super().__init__(parent)

        self.expanded_width = expanded_width
        self.collapsed_width = collapsed_width
        self._collapsed = False

        self.setFixedWidth(self.expanded_width)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack)

        # --- Expanded page: header (title + collapse arrow) + content ---
        expanded_page = QWidget()
        expanded_layout = QVBoxLayout(expanded_page)
        expanded_layout.setContentsMargins(4, 4, 4, 4)
        expanded_layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{title}</b>"))
        header.addStretch()
        collapse_btn = QToolButton()
        collapse_btn.setText("«")
        collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        collapse_btn.setToolTip("Collapse")
        collapse_btn.clicked.connect(self.collapse)
        header.addWidget(collapse_btn)
        expanded_layout.addLayout(header)

        expanded_layout.addWidget(content_widget)
        self.stack.addWidget(expanded_page)

        # --- Collapsed page: just the vertical tab, click to expand ---
        collapsed_page = QWidget()
        collapsed_layout = QVBoxLayout(collapsed_page)
        collapsed_layout.setContentsMargins(0, 0, 0, 0)
        self.expand_tab = VerticalTabButton(title)
        self.expand_tab.clicked.connect(self.expand)
        collapsed_layout.addWidget(self.expand_tab)
        self.stack.addWidget(collapsed_page)

        # Animation that drives the width change
        self._animation = QVariantAnimation()
        self._animation.setDuration(animation_ms)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._animation.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))

    def _animate_to(self, target_width):
        self._animation.stop()
        self._animation.setStartValue(self.width())
        self._animation.setEndValue(target_width)
        self._animation.start()

    def is_collapsed(self) -> bool:
        return self._collapsed

    def collapse(self):
        if self._collapsed:
            return
        self._collapsed = True
        self._animate_to(self.collapsed_width)
        # Switch to the thin-tab page once it's shrunk down
        self._animation.finished.connect(self._show_collapsed_page)

    def _show_collapsed_page(self):
        self.stack.setCurrentIndex(1)
        self._animation.finished.disconnect(self._show_collapsed_page)

    def expand(self):
        if not self._collapsed:
            return
        self._collapsed = False
        self.stack.setCurrentIndex(0)  # show content immediately, then grow into it
        self._animate_to(self.expanded_width)
