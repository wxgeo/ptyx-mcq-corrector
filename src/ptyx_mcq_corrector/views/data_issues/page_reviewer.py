from enum import Flag
from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy

from ptyx_mcq.scan.data.documents import Page

from ptyx_mcq_corrector.enhanced_widget import EnhancedWidget
from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.issues_widget.issues_model import IssuesModel
from ptyx_mcq_corrector.issues_widget.issue_info import IssueType, IssueInfo
from ptyx_mcq_corrector.issues_widget.issues_view import IssuesViewer
from ptyx_mcq_corrector.views.data_issues.cbx_reviewer import CheckboxesReviewer
from ptyx_mcq_corrector.views.data_issues.name_editor import NameEditor
from ptyx_mcq_corrector.tools import update_ui

if TYPE_CHECKING:
    pass


class Components(Flag):
    NONE = 0
    NAME_EDITOR = 1
    CBX_REVIEWER = 2
    BOTH = 3


class DataView(EnhancedWidget):
    # main_window: "McqCorrectorMainWindow"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        main_layout = QHBoxLayout(self)
        self.issues_viewer = IssuesViewer(self)
        main_layout.addWidget(self.issues_viewer, 0)
        self.issues_model = IssuesModel(STATE)
        self.issues_viewer.setModel(self.issues_model)

        layout = QVBoxLayout()
        self.name_editor = NameEditor(self)
        self.name_editor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.name_editor)
        self.page_view = CheckboxesReviewer(self)
        self.page_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.page_view)

        main_layout.addLayout(layout, 1)

        self.components_to_display: Components = Components.NONE
        self.update_view()
        self.page_view.previous_page_requested.connect(self.issues_viewer.move_to_previous_index)
        self.page_view.next_page_requested.connect(self.issues_viewer.move_to_next_index)
        self.page_view.esc_requested.connect(self.issues_viewer.setFocus)

    @staticmethod
    def _name_suggestions() -> list[str]:
        return sorted([student.to_text() for student in STATE.students])

    def update_view(self):
        self.name_editor.setVisible(Components.NAME_EDITOR in self.components_to_display)
        self.name_editor.update_suggestions()

        self.page_view.checkbox_review = Components.CBX_REVIEWER in self.components_to_display
        match self.components_to_display:
            case Components.BOTH:
                color = "magenta"
            case Components.NAME_EDITOR:
                color = "crimson"
            case Components.CBX_REVIEWER:
                color = "cornflowerblue"
            case _:
                color = "black"
        self.page_view.focus_rect_color = QColor(color)

    def update_issues(self) -> None:
        self.issues_viewer.update_issues()

    @property
    def page(self) -> Page:
        return self.page_view.page

    @page.setter
    def page(self, page: Page | None) -> None:
        self.page_view.page = page
        self.name_editor.set_current_student(None if page is None else page.pic.student)

    def validate_issue(self):
        print("Validating issue")
        if (issue := STATE.current_issue) is not None:
            if self.issues_model.validate(issue.index):
                self.issues_viewer.move_to_next_index()

    def validate_all_answers(self):
        for issue in self.issues_model.issues:
            if issue.type == IssueType.AMBIGUOUS_ANSWERS:
                self.issues_model.validate(issue.index)

    @update_ui
    def on_issue_selected(self, issue: IssueInfo) -> bool:
        assert issue is not None
        STATE.current_issue = issue  # To do at first!
        parser = STATE.parser
        assert parser is not None
        doc = parser.scan_data.used_docs_index[issue.doc_id]
        # Be careful to select the reviewer only *AFTER* the state have been changed.
        match issue.type:
            case IssueType.NAMES:
                self.page = doc.first_page
            case IssueType.AMBIGUOUS_ANSWERS:
                page_num = issue.page_num
                assert page_num is not None
                page = doc.pages_index[page_num]
                self.page = page
        self.page_view.setFocus()
        return True
