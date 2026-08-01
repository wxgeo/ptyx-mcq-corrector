from enum import Enum
from typing import Mapping

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from ptyx_mcq.scan.data.conflict_gestion.data_check.check import DataCheckResult
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.check import IntegrityCheckResult
from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum

from ptyx_mcq_corrector.internal_state import AppState
from ptyx_mcq_corrector.review.issues.issue_info import IssueType, IssueInfo

FoundIssues = dict[DocumentId, list[PageNum]] | list[DocumentId]

ISSUE_ROLE = Qt.ItemDataRole.UserRole + 1
STATE_ROLE = Qt.ItemDataRole.UserRole + 2


class IssueState(Enum):
    PENDING = "pending"
    FIXED = "fixed"


def _add_header(parent: QStandardItem, title: str) -> QStandardItem:
    """
    Add a header to the model.

    A header is non-selectable.
    """
    header = QStandardItem(title)
    header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    parent.appendRow(header)
    return header


def _add_item(
    parent: QStandardItem, title: str, issue_type: IssueType, doc_id: DocumentId, page: PageNum | None
) -> QStandardItem:
    parent.appendRow(item := QStandardItem(title))
    item.setData(IssueInfo(index=item.index(), type=issue_type, doc_id=doc_id, page_num=page), ISSUE_ROLE)
    # IssueState is used to apply the appropriate style.
    item.setData(IssueState.PENDING, STATE_ROLE)
    return item


def _add_category(root: QStandardItem, issues_type: IssueType, results: FoundIssues) -> None:
    """
    Add the issues of the same type to the model.
    """
    category = _add_header(root, str(issues_type))
    if isinstance(results, dict):
        for doc_id, pages in results.items():
            doc = _add_header(category, f"Document {doc_id}")
            for page in pages:
                _add_item(doc, f"Page {page}", issues_type, doc_id, page)
    else:
        assert isinstance(results, list)
        for doc_id in results:
            _add_item(category, f"Document {doc_id}", issues_type, doc_id, None)
    assert root is not None


class IssuesModel(QStandardItemModel):
    def __init__(self, state: "AppState"):
        super().__init__()
        self.state = state
        self.current_doc: DocumentId | None = None
        self.current_page: PageNum | None = None
        self.title: str = ""

    def update_model(self) -> bool:
        """
        Update the state of the model.

        Return `True` if any issues were found, `False` otherwise.
        """
        issues: IntegrityCheckResult | DataCheckResult | None
        categories: dict[IssueType, FoundIssues]
        if self.state.integrity_issues_detected:
            issues = self.state.integrity_issues
            assert isinstance(issues, IntegrityCheckResult)
            categories = {
                IssueType.DUPLICATES: issues.duplicates,
                IssueType.MISSING_PAGES: issues.missing_pages,
            }
            return self._fill_model("Integrity issues", categories)
        elif self.state.data_issues_detected:
            issues = self.state.data_issues
            assert isinstance(issues, DataCheckResult)
            categories = {
                IssueType.NAMES: issues.names_to_review,
                IssueType.AMBIGUOUS_ANSWERS: issues.ambiguous_answers_by_doc,
            }
            return self._fill_model("Data issues", categories)
        return False

    def _fill_model(
        self,
        title: str,
        categories: Mapping[IssueType, FoundIssues],
    ):
        """
        Fill the model with detected issues.

        Return `True` if any issues were found, `False` otherwise.
        """
        self.clear()
        self.title = title
        # self.setHorizontalHeaderLabels([title])
        root = self.invisibleRootItem()  # top of the tree
        for issues_type, results in categories.items():
            assert root is not None
            _add_category(root, issues_type, results)
        return True

    def validate(self, index: QModelIndex) -> bool:
        if index.flags() & Qt.ItemFlag.ItemIsSelectable:
            item = self.itemFromIndex(index)
            if item is not None:
                assert (parser := self.state.parser) is not None
                issue: IssueInfo = item.data(ISSUE_ROLE)
                if issue.validate_state(parser.scan_data):
                    # Mark the issue as fixed.
                    item.setData(IssueState.FIXED, STATE_ROLE)
                    print("Issue marked as fixed.")
                    return True
                else:
                    print("Issue does not seem to be fixed yet.")
        return False

    @property
    def issues(self) -> list[IssueInfo]:
        issues: list[IssueInfo] = []
        for row in range(self.rowCount()):
            item = self.item(row)
            assert item is not None
            issue: IssueInfo | None = item.data(ISSUE_ROLE)
            if isinstance(issue, IssueInfo):
                issues.append(issue)
        return issues
