from enum import StrEnum

from PyQt6.QtGui import QStandardItemModel, QStandardItem

from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum
from ptyx_mcq_corrector.internal_state import State


class IssuesTypes(StrEnum):
    NAMES = "Names"
    AMBIGUOUS_ANSWERS = "Ambiguous answers"
    MISSING_PAGES = "Missing pages"
    DUPLICATES = "Duplicates"


class IssuesModel:
    def __init__(self, state: State):
        self.state = state
        self.tree_model: QStandardItemModel = QStandardItemModel()
        self.current_doc: DocumentId | None = None
        self.current_page: PageNum | None = None

    def update(self) -> None:
        if self.state.integrity_issues_detected:
            self._set_integrity_issues_model()
        elif self.state.data_issues_detected:
            self._set_data_issues_model()

    def _add_folder(
        self, root: QStandardItem, issues_type: IssuesTypes, results: dict[DocumentId, list[PageNum]]
    ) -> None:
        folder = QStandardItem(str(issues_type))
        for doc_id, pages in results.items():
            doc = QStandardItem(f"Document {doc_id}")
            folder.appendRow(doc)
            for page in pages:
                doc.appendRow(item := QStandardItem(f"Pages {page}"))
                item.setData({"type": issues_type, "doc": doc_id, "page": page})
        assert root is not None
        root.appendRow(folder)

    def _prepare_model(self, title: str, results: object) -> QStandardItem | None:
        if results is None:
            return None
        (model := self.tree_model).clear()
        model.setHorizontalHeaderLabels([title])
        return model.invisibleRootItem()  # top of the tree

    def _set_integrity_issues_model(self) -> None:
        integrity_check_results = self.state.integrity_issues
        root = self._prepare_model("Integrity issues", integrity_check_results)
        if root is None:
            return
        assert integrity_check_results is not None
        categories = {
            IssuesTypes.DUPLICATES: integrity_check_results.duplicates,
            IssuesTypes.MISSING_PAGES: integrity_check_results.missing_pages,
        }
        for issues_type, results in categories.items():
            assert root is not None
            self._add_folder(root, issues_type, results)

    def _set_data_issues_model(self):
        data_issues = self.state.data_issues
        root = self._prepare_model("Integrity issues", data_issues)
        if root is None:
            return
        assert data_issues is not None
        folder = QStandardItem("Names issues")
        for doc_id in data_issues.names_to_review:
            folder.appendRow(item := QStandardItem(f"Document {doc_id}"))
            item.setData({"type": IssuesTypes.NAMES, "doc": doc_id})
        root.appendRow(folder)

        self._add_folder(root, IssuesTypes.AMBIGUOUS_ANSWERS, data_issues.ambiguous_answers_by_doc)
