from enum import IntEnum
from typing import TYPE_CHECKING

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStackedWidget, QWidget, QLabel, QVBoxLayout, QHBoxLayout

from ptyx_mcq_corrector.app_state import STATE, State
from ptyx_mcq_corrector.issues_widget.issue_info import IssueType
from ptyx_mcq_corrector.scores.scores_view import ScoresView
from ptyx_mcq_corrector.views.corrections.main_widget import CorrectionsView
from ptyx_mcq_corrector.views.default.main_widget import DefaultView
from ptyx_mcq_corrector.views.integrity_issues.main_widget import IntegrityView
from ptyx_mcq_corrector.views.search_results.main_widget import SearchView

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow
from ptyx_mcq_corrector.views.data_issues.page_reviewer import DataView, Components


class ViewMode(IntEnum):
    DEFAULT = 0
    INTEGRITY_ISSUES = 1
    DATA_ISSUES = 2
    SEARCH_RESULTS = 3
    SCORES = 4
    CORRECTIONS = 5


DEFAULTS_VIEW_MODES: dict[State, ViewMode] = {
    State.NO_SCAN: ViewMode.DEFAULT,
    State.SCAN_IN_PROGRESS: ViewMode.DEFAULT,
    State.INTEGRITY_ISSUES: ViewMode.INTEGRITY_ISSUES,
    State.DATA_ISSUES: ViewMode.DATA_ISSUES,
    State.VALIDATED: ViewMode.SCORES,
    State.SCORES_COMPUTED: ViewMode.SCORES,
    State.CORRECTIONS_GENERATED: ViewMode.CORRECTIONS,
}

ALLOWED_STATES: dict[ViewMode, list[State]] = {
    ViewMode.DEFAULT: [State.NO_SCAN, State.SCAN_IN_PROGRESS],
    ViewMode.INTEGRITY_ISSUES: [State.INTEGRITY_ISSUES],
    ViewMode.DATA_ISSUES: [State.DATA_ISSUES],
    ViewMode.SEARCH_RESULTS: [
        State.INTEGRITY_ISSUES,
        State.DATA_ISSUES,
        State.VALIDATED,
        State.SCORES_COMPUTED,
        State.CORRECTIONS_GENERATED,
    ],
    ViewMode.SCORES: [State.VALIDATED, State.SCORES_COMPUTED, State.CORRECTIONS_GENERATED],
    ViewMode.CORRECTIONS: [State.CORRECTIONS_GENERATED],
}


class MainArea(QStackedWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._parent: McqCorrectorMainWindow = parent  # type: ignore
        self.default_view = DefaultView(self)
        self.addWidget(self.default_view)
        self.integrity_view = IntegrityView(self)
        self.addWidget(self.integrity_view)
        self.data_view = DataView(self)
        self.addWidget(self.data_view)
        self.search_view = SearchView(self)
        self.addWidget(self.search_view)
        self.scores_view = ScoresView(self)
        self.addWidget(self.scores_view)
        self.corrections_view = CorrectionsView(self)
        self.addWidget(self.corrections_view)
        self._view_mode: ViewMode = ViewMode.DEFAULT

    @property
    def view_mode(self) -> ViewMode:
        return self._view_mode

    @view_mode.setter
    def view_mode(self, mode: ViewMode) -> None:
        assert STATE.state in ALLOWED_STATES[mode], STATE.state
        self._view_mode = mode

    def update_view(self) -> None:
        # TODO: handle scores' view
        self._parent.menuReview.setEnabled(self.view_mode != ViewMode.DEFAULT)
        is_review = self.view_mode in (ViewMode.INTEGRITY_ISSUES, ViewMode.DATA_ISSUES)
        for action in [
            self._parent.actionPrevious,
            self._parent.actionNext,
            self._parent.actionValidate,
            self._parent.actionValidate_all_answers,
            self._parent.actionRefresh,
        ]:
            action.setVisible(is_review)
            action.setEnabled(is_review)
        print(self.view_mode)
        match self.view_mode:
            case ViewMode.DEFAULT:
                self._update_header()

            case ViewMode.INTEGRITY_ISSUES | ViewMode.DATA_ISSUES:
                issue = STATE.current_issue
                print(issue)
                if issue is None:
                    self.data_view.page = None
                    self.data_view.components_to_display = Components.CBX_REVIEWER
                else:
                    match issue.type:
                        case IssueType.AMBIGUOUS_ANSWERS:
                            self.data_view.components_to_display = Components.CBX_REVIEWER
                            self.data_view.update_view()
                        case IssueType.NAMES:
                            self.data_view.components_to_display = Components.NAME_EDITOR
                            self.data_view.update_view()
                        case IssueType.DUPLICATES:
                            ...  # TODO
                        case IssueType.MISSING_PAGES:
                            ...  # TODO

            case ViewMode.SEARCH_RESULTS:
                ...  # TODO
            case ViewMode.SCORES:
                ...  # TODO
            case ViewMode.CORRECTIONS:
                ...  # TODO

            case _:
                raise NotImplementedError
        self.setCurrentIndex(self.view_mode)

    def _update_header(self) -> None:
        label = self.default_view.header_label
        if STATE.current_file is None:
            label.setText("No document")

        elif STATE.state == State.SCAN_IN_PROGRESS:
            msg = f"Starting scan of '{STATE.current_file}'..."
            print(msg)
            label.setText(msg)

        else:
            label.setText(STATE.current_file_shortname)
            # Any non-null value is OK for `href`, but it can't be left empty, else Qt doesn't generate a link at all.
            label.setText(
                "<p style='text-align:center'>Document <i><b>"
                f"<a href='#'>{STATE.current_file_shortname}</a>"
                "</b></i> selected.</p>"
                "<p style='text-align:center;font-size:small'>Press <b>F5</b> to start scanning.</p>"
            )
            try:
                label.linkActivated.disconnect()
            except TypeError:
                pass  # no connection existed yet
            label.linkActivated.connect(lambda _: self._parent.file_events_handler.open_file())
            label.setOpenExternalLinks(False)
