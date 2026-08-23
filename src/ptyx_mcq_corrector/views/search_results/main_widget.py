from PyQt6.QtWidgets import QWidget

from ptyx_mcq_corrector.custom_widgets.page_reviewer.page_reviewer import PageReviewer, Components


class SearchView(PageReviewer):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.components_to_display = Components.SEARCH_BAR
