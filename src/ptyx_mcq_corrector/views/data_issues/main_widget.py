from PyQt6.QtWidgets import QWidget

from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.items_list.types import (
    ItemStatus,
    CategoryTitle,
    CategoryItemData,
    DocTitle,
    PageTitle,
    DocItemData,
    PageItemData,
)
from ptyx_mcq_corrector.custom_widgets.page_reviewer.page_reviewer import PageReviewer


class DataView(PageReviewer):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

    @property
    def _name_issues(self) -> CategoryItemData:
        docs: list[DocItemData] = []
        assert STATE.data_issues is not None
        assert STATE.parser is not None
        for doc_id in STATE.data_issues.names_to_review:
            doc = STATE.parser.scan_data.used_docs_index[doc_id]
            docs.append(DocItemData(name=DocTitle(f"Document {doc_id}"), doc=doc))
        return CategoryItemData(name=CategoryTitle.NAMES, docs=docs, display_pages=False)

    @property
    def _ambiguous_answers(self) -> CategoryItemData:
        assert STATE.parser is not None
        assert STATE.data_issues is not None
        docs_index = STATE.parser.scan_data.used_docs_index
        docs: list[DocItemData] = []
        for doc_id, page_nums in STATE.data_issues.ambiguous_answers_by_doc.items():
            doc = docs_index[doc_id]
            pages: list[PageItemData] = []
            for page_num in page_nums:
                page = doc.pages_index[page_num]
                pages.append(PageItemData(name=PageTitle(f"Page {page_num}"), page=page))
            docs.append(DocItemData(name=DocTitle(f"Document {doc_id}"), doc=doc, pages=pages))
        return CategoryItemData(name=CategoryTitle.AMBIGUOUS_ANSWERS, docs=docs, display_pages=True)

    def update_issues(self) -> None:
        self.update_items(self._name_issues, self._ambiguous_answers)

    def _prepare_view(self) -> None:
        """Specific actions to do between updating the model and updating view."""
        for item_info in self.issues_model.selectable_items:
            print(item_info)
            item_info.status = ItemStatus.FAILURE
