from PyQt6.QtWidgets import QWidget

from ptyx_mcq_corrector.custom_widgets.page_reviewer.page_reviewer import PageReviewer


class DataView(PageReviewer):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
