from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ptyx_mcq_corrector.tools import not_none
from ptyx_mcq_corrector.views.scores.qpdf_toolbar import PdfToolBar


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWheelEvent


class ZoomablePdfView(QPdfView):
    """QPdfView with Ctrl+wheel zoom and zoom steps based on the real zoom level."""

    ZOOM_STEP = 1.25
    ZOOM_MIN, ZOOM_MAX = 0.1, 5.0
    ZOOM_WHEEL_MODIFIER = Qt.KeyboardModifier.ControlModifier

    def effective_zoom(self) -> float:
        """The zoom factor actually applied to the current page.

        In fit modes, zoomFactor() is NOT the real scale, so recompute it
        the way QPdfView does: available viewport size divided by the page
        size in screen pixels at 100%.
        """
        document = self.document()
        mode = self.zoomMode()
        if mode == QPdfView.ZoomMode.Custom or document is None or document.pageCount() == 0:
            return self.zoomFactor()
        page = not_none(self.pageNavigator()).currentPage()
        size = document.pagePointSize(page)  # in points (1/72 inch)
        px_per_point = not_none(self.screen()).logicalDotsPerInch() / 72.0
        margins = self.documentMargins()
        viewport = self.viewport()
        assert viewport is not None

        zoom_w = (viewport.width() - margins.left() - margins.right()) / (size.width() * px_per_point)
        if mode == QPdfView.ZoomMode.FitToWidth:
            return zoom_w
        zoom_h = (viewport.height() - margins.top() - margins.bottom()) / (size.height() * px_per_point)
        return min(zoom_w, zoom_h)

    def zoom_by(self, multiplier: float) -> None:
        factor = self.effective_zoom() * multiplier  # compute BEFORE changing mode
        factor = max(self.ZOOM_MIN, min(self.ZOOM_MAX, factor))
        self.setZoomMode(QPdfView.ZoomMode.Custom)
        self.setZoomFactor(factor)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        assert event is not None
        if event.modifiers() & self.ZOOM_WHEEL_MODIFIER:
            delta = event.angleDelta().y()
            if delta:
                # 120 units = one standard notch; touchpads send smaller
                # values, so the zoom stays proportional and smooth.
                self.zoom_by(self.ZOOM_STEP ** (delta / 120))
            event.accept()
        else:
            super().wheelEvent(event)  # normal scrolling (incl. Shift+wheel)


class SmallPdfWidget(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = ZoomablePdfView(self)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.toolbar = PdfToolBar(self)
        # Layout
        self._layout = QVBoxLayout()
        self._layout.addWidget(self.toolbar)
        self._layout.addWidget(self.pdf_view)
        self.setLayout(self._layout)
