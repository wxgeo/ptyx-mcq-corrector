from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QPointF, QSize, Qt
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtWidgets import QLabel, QSpinBox, QToolBar

if TYPE_CHECKING:
    pass


class PdfToolBar(QToolBar):
    """Page navigation, zoom and page-mode controls for a SmallPdfWidget."""

    ZOOM_STEP = 1.25
    ZOOM_MIN, ZOOM_MAX = 0.1, 5.0
    ICON_SIZE = 18

    def __init__(self, pdf_widget: "SmallPdfWidget", parent=None):
        super().__init__("PDF controls", parent)
        self.pdf_widget = pdf_widget
        self.view = pdf_widget.pdf_view
        self.document = pdf_widget.pdf_document
        self.navigator = self.view.pageNavigator()
        self.setMovable(False)
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # --- Page navigation:  ‹ [1] / 6 › ---
        self.prev_action = QAction("Previous page", self)
        self.prev_action.setToolTip("Previous page")
        self.prev_action.triggered.connect(lambda: self._go_to(self.navigator.currentPage() - 1))

        self.next_action = QAction("Next page", self)
        self.next_action.setToolTip("Next page")
        self.next_action.triggered.connect(lambda: self._go_to(self.navigator.currentPage() + 1))

        self.page_spin = QSpinBox()
        self.page_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_spin.setKeyboardTracking(False)  # only fire on Enter / focus out
        self.page_spin.setMinimum(1)
        self.page_spin.setToolTip("Current page (editable)")
        self.page_spin.valueChanged.connect(lambda n: self._go_to(n - 1))

        self.page_count_label = QLabel(" / 0 ")

        # --- Page mode (mutually exclusive) ---
        self.single_action = QAction("Single page", self, checkable=True)
        self.multi_action = QAction("Continuous", self, checkable=True)
        self.single_action.setToolTip("Show one page at a time")
        self.multi_action.setToolTip("Show all pages in a scrollable column")
        mode_group = QActionGroup(self)
        mode_group.addAction(self.single_action)
        mode_group.addAction(self.multi_action)
        self.single_action.triggered.connect(lambda: self.view.setPageMode(QPdfView.PageMode.SinglePage))
        self.multi_action.triggered.connect(lambda: self.view.setPageMode(QPdfView.PageMode.MultiPage))

        # --- Zoom ---
        # Both fit actions are unchecked when the zoom is custom.
        self.fit_width_action = QAction("Fit width", self, checkable=True)
        self.fit_page_action = QAction("Fit page", self, checkable=True)
        fit_group = QActionGroup(self)
        fit_group.addAction(self.fit_width_action)
        fit_group.addAction(self.fit_page_action)
        self.fit_width_action.triggered.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        self.fit_page_action.triggered.connect(lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitInView))

        self.zoom_out_action = QAction("Zoom out", self)
        self.zoom_out_action.setToolTip("Zoom out (Ctrl+-)")
        self.zoom_out_action.setShortcuts([QKeySequence("Ctrl+-")])
        self.zoom_out_action.triggered.connect(lambda: self._step_zoom(1 / self.ZOOM_STEP))

        self.zoom_in_action = QAction("Zoom in", self)
        self.zoom_in_action.setToolTip("Zoom in (Ctrl++)")
        self.zoom_in_action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self.zoom_in_action.triggered.connect(lambda: self._step_zoom(self.ZOOM_STEP))

        # --- Icons ---
        self._update_icons()

        # --- Layout ---
        self.addAction(self.prev_action)
        self.addWidget(self.page_spin)
        self.addWidget(self.page_count_label)
        self.addAction(self.next_action)
        self.addSeparator()
        self.addAction(self.single_action)
        self.addAction(self.multi_action)
        self.addSeparator()
        self.addAction(self.fit_width_action)
        self.addAction(self.fit_page_action)
        self.addAction(self.zoom_out_action)
        self.addAction(self.zoom_in_action)

        # --- Cached state, fed by the view's signals ---
        self._page_count = self.document.pageCount()
        self._current_page = self.navigator.currentPage()

        # --- Keep toolbar in sync with the view / document ---
        self.navigator.currentPageChanged.connect(self._on_page_changed)
        self.document.pageCountChanged.connect(self._on_page_count_changed)
        self.view.pageModeChanged.connect(self._on_page_mode_changed)
        self.view.zoomModeChanged.connect(self._on_zoom_mode_changed)

        self._refresh_page_controls()
        self._on_page_mode_changed(self.view.pageMode())
        self._on_zoom_mode_changed(self.view.zoomMode())

    # ------------------------------------------------------------------ #
    # Icons
    # ------------------------------------------------------------------ #
    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # Redraw icons when the theme changes (e.g. light <-> dark mode).
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "zoom_in_action"):
            self._update_icons()

    def _update_icons(self) -> None:
        self.prev_action.setIcon(self._make_icon("prev"))
        self.next_action.setIcon(self._make_icon("next"))
        self.zoom_out_action.setIcon(self._make_icon("zoom_out"))
        self.zoom_in_action.setIcon(self._make_icon("zoom_in"))

    def _make_icon(self, kind: str) -> QIcon:
        """Draw a simple line icon on a 24x24 grid, in the palette's colors."""
        palette = self.palette()
        dpr = self.devicePixelRatioF()
        icon = QIcon()
        for mode, group in (
            (QIcon.Mode.Normal, QPalette.ColorGroup.Active),
            (QIcon.Mode.Disabled, QPalette.ColorGroup.Disabled),
        ):
            color = palette.color(group, QPalette.ColorRole.ButtonText)

            pixmap = QPixmap(int(24 * dpr), int(24 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)

            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(color, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)

            if kind == "prev":  # chevron pointing left
                p.drawPolyline([QPointF(15, 5), QPointF(8, 12), QPointF(15, 19)])
            elif kind == "next":  # chevron pointing right
                p.drawPolyline([QPointF(9, 5), QPointF(16, 12), QPointF(9, 19)])
            else:  # magnifying glass with "+" or "-"
                p.drawEllipse(QPointF(10, 10), 6.5, 6.5)  # lens
                p.drawLine(QPointF(15, 15), QPointF(20.5, 20.5))  # handle
                p.drawLine(QPointF(7, 10), QPointF(13, 10))  # horizontal bar
                if kind == "zoom_in":
                    p.drawLine(QPointF(10, 7), QPointF(10, 13))  # vertical bar
            p.end()

            icon.addPixmap(pixmap, mode)
        return icon

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _go_to(self, page: int) -> None:
        """Jump to a 0-based page index (clamped)."""
        if self._page_count == 0:
            return
        page = max(0, min(self._page_count - 1, page))
        if page != self._current_page:
            self.navigator.jump(page, QPointF(), self.navigator.currentZoom())
        self._refresh_page_controls()  # also resets the spin box if the input was out of range

    # ------------------------------------------------------------------ #
    # Zoom
    # ------------------------------------------------------------------ #
    def _effective_zoom(self) -> float:
        """The zoom factor actually applied to the current page.

        In fit modes, QPdfView.zoomFactor() is NOT the real scale, so we
        recompute it the same way QPdfView does: available viewport size
        divided by the page size in screen pixels at 100%.
        """
        mode = self.view.zoomMode()
        if mode == QPdfView.ZoomMode.Custom or self.document.pageCount() == 0:
            return self.view.zoomFactor()

        page = self.navigator.currentPage()
        size = self.document.pagePointSize(page)  # in points (1/72 inch)
        px_per_point = self.view.screen().logicalDotsPerInch() / 72.0
        margins = self.view.documentMargins()
        viewport = self.view.viewport()

        zoom_w = (viewport.width() - margins.left() - margins.right()) / (size.width() * px_per_point)
        if mode == QPdfView.ZoomMode.FitToWidth:
            return zoom_w
        zoom_h = (viewport.height() - margins.top() - margins.bottom()) / (size.height() * px_per_point)
        return min(zoom_w, zoom_h)

    def _step_zoom(self, multiplier: float) -> None:
        factor = self._effective_zoom() * multiplier  # compute BEFORE changing mode
        factor = max(self.ZOOM_MIN, min(self.ZOOM_MAX, factor))
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(factor)

    # ------------------------------------------------------------------ #
    # Sync view -> toolbar (slots only use their arguments and cached state)
    # ------------------------------------------------------------------ #
    def _on_page_changed(self, page: int) -> None:
        self._current_page = page
        self._refresh_page_controls()

    def _on_page_count_changed(self, count: int) -> None:
        self._page_count = count
        self._refresh_page_controls()

    def _refresh_page_controls(self) -> None:
        count, current = self._page_count, self._current_page
        has_doc = count > 0

        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, count))
        self.page_spin.setValue(current + 1 if has_doc else 1)
        self.page_spin.blockSignals(False)

        self.page_count_label.setText(f" / {count} ")
        self.page_spin.setEnabled(has_doc)
        self.prev_action.setEnabled(has_doc and current > 0)
        self.next_action.setEnabled(has_doc and current < count - 1)

    def _on_page_mode_changed(self, mode) -> None:
        single = mode == QPdfView.PageMode.SinglePage
        self.single_action.setChecked(single)
        self.multi_action.setChecked(not single)

    def _on_zoom_mode_changed(self, mode) -> None:
        self.fit_width_action.setChecked(mode == QPdfView.ZoomMode.FitToWidth)
        self.fit_page_action.setChecked(mode == QPdfView.ZoomMode.FitInView)
