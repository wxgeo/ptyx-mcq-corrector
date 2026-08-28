from PyQt6.QtWidgets import QWidget

from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.items_list.types import (
    CategoryItemData,
    DocItemData,
    PageItemData,
    PageTitle,
    DocTitle,
    CategoryTitle,
)
from ptyx_mcq_corrector.custom_widgets.page_reviewer.page_reviewer import PageReviewer, Components


class SearchView(PageReviewer):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.components_to_display = Components.SEARCH_BAR

    def _docs(self) -> CategoryItemData:
        assert STATE.parser is not None
        assert STATE.data_issues is not None
        docs: list[DocItemData] = []
        for doc in STATE.parser.scan_data.sorted_by("student"):
            pages: list[PageItemData] = []
            for page_num, page in doc.pages_index.items():
                page = doc.pages_index[page_num]
                pages.append(PageItemData(name=PageTitle(f"Page {page_num}"), page=page))
            docs.append(
                DocItemData(
                    name=DocTitle(f"{doc.student_name} ({doc.student_id}) - #{doc.doc_id}"),
                    doc=doc,
                    pages=pages,
                )
            )
        return CategoryItemData(name=CategoryTitle.NONE, docs=docs, display_pages=True)

    def update_docs(self):
        self.update_items(self._docs())
