from enum import StrEnum

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum
from ptyx_mcq_corrector.internal_state import State


FoundIssues = dict[DocumentId, list[PageNum]] | list[DocumentId]


class IssuesTypes(StrEnum):
    NAMES = "Names issues"
    AMBIGUOUS_ANSWERS = "Ambiguous answers"
    MISSING_PAGES = "Missing pages"
    DUPLICATES = "Duplicates"


def _add_header(parent: QStandardItem, title: str) -> QStandardItem:
    """
    Add a header to the model.

    A header is non-selectable.
    """
    header = QStandardItem(title)
    header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    parent.appendRow(header)
    return header


def _add_category(root: QStandardItem, issues_type: IssuesTypes, results: FoundIssues) -> None:
    """
    Add the issues of the same type to the model.
    """
    category = _add_header(root, str(issues_type))
    if isinstance(results, dict):
        for doc_id, pages in results.items():
            doc = _add_header(category, f"Document {doc_id}")
            for page in pages:
                doc.appendRow(item := QStandardItem(f"Pages {page}"))
                item.setData({"type": issues_type, "doc": doc_id, "page": page})
    else:
        assert isinstance(results, list)
        for doc_id in results:
            category.appendRow(item := QStandardItem(f"Document {doc_id}"))
            item.setData({"type": IssuesTypes.NAMES, "doc": doc_id})
    assert root is not None


class IssuesModel:
    def __init__(self, state: State):
        self.state = state
        self.tree_model: QStandardItemModel = QStandardItemModel()
        self.current_doc: DocumentId | None = None
        self.current_page: PageNum | None = None

    def update(self) -> bool:
        """
        Update the state of the model.

        Return `True` if any issues were found, `False` otherwise.
        """
        if self.state.integrity_issues_detected:
            issues = self.state.integrity_issues
            assert issues is not None
            categories = {
                IssuesTypes.DUPLICATES: issues.duplicates,
                IssuesTypes.MISSING_PAGES: issues.missing_pages,
            }
            return self._fill_model("Integrity issues", categories)
        elif self.state.data_issues_detected:
            issues = self.state.data_issues
            assert issues is not None
            categories = {
                IssuesTypes.DUPLICATES: issues.names_to_review,
                IssuesTypes.MISSING_PAGES: issues.ambiguous_answers_by_doc,
            }
            return self._fill_model("Data issues", categories)
        return False

    def _fill_model(
        self,
        title: str,
        categories: dict[IssuesTypes, FoundIssues],
    ):
        """
        Fill the model with detected issues.

        Return `True` if any issues were found, `False` otherwise.
        """
        (model := self.tree_model).clear()
        model.setHorizontalHeaderLabels([title])
        root = model.invisibleRootItem()  # top of the tree
        for issues_type, results in categories.items():
            assert root is not None
            _add_category(root, issues_type, results)
        return True
