from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStackedWidget, QWidget, QLabel, QVBoxLayout, QHBoxLayout

from ptyx_mcq_corrector.internal_state import STATE, ScanState
from ptyx_mcq_corrector.review.issues.issue_info import IssueType

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow
from ptyx_mcq_corrector.review.page.page_reviewer import PageReviewer, Components


class ViewMode(Enum):
    DEFAULT = auto()
    REVIEW = auto()
    SCORES = auto()


class DefaultView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        horizontal = QHBoxLayout()
        spacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        horizontal.addSpacerItem(spacer)
        self.header_label = QLabel(parent=self)
        self.header_label.setTextFormat(Qt.TextFormat.RichText)
        self.header_label.setOpenExternalLinks(True)
        self.header_label.setObjectName("header_label")
        horizontal.addWidget(self.header_label)
        spacer2 = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        horizontal.addSpacerItem(spacer2)
        main_layout.addLayout(horizontal)
        spacer3 = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding
        )
        main_layout.addSpacerItem(spacer3)


class MainArea(QStackedWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._parent: McqCorrectorMainWindow = parent  # type: ignore
        self.default_view = DefaultView(self)
        self.setObjectName("main_area")
        self.addWidget(self.default_view)
        self.page_reviewer = PageReviewer(self)
        self.page_reviewer.setObjectName("page_reviewer")
        self.addWidget(self.page_reviewer)

    @property
    def view_mode(self) -> ViewMode:
        if STATE.scan_state == ScanState.DONE:
            return ViewMode.REVIEW
            # TODO: handle scores' view
        return ViewMode.DEFAULT

    def update_view(self) -> None:
        # TODO: handle scores' view
        is_review = self.view_mode == ViewMode.REVIEW
        self._parent.menuReview.setEnabled(is_review)
        for action in [self._parent.actionPrevious, self._parent.actionNext, self._parent.actionValidate]:
            action.setVisible(is_review)
            action.setEnabled(is_review)
        print(self.view_mode)
        match self.view_mode:
            case ViewMode.DEFAULT:
                index = 0
                self._update_header()

            case ViewMode.REVIEW:
                issue = STATE.current_issue
                print(issue)
                if issue is None:
                    self.page_reviewer.page = None
                    self.page_reviewer.components_to_display = Components.CBX_REVIEWER
                    index = 1
                else:
                    match issue.type:
                        case IssueType.AMBIGUOUS_ANSWERS:
                            index = 1
                            self.page_reviewer.components_to_display = Components.CBX_REVIEWER
                            self.page_reviewer.update_view()
                        case IssueType.NAMES:
                            index = 1
                            self.page_reviewer.components_to_display = Components.NAME_EDITOR
                            self.page_reviewer.update_view()
                        case IssueType.DUPLICATES:
                            index = 2
                            ...  # TODO
                        case IssueType.MISSING_PAGES:
                            index = 3
                            ...  # TODO

            case ViewMode.SCORES:
                index = 4
                # TODO: to implement
            case _:
                raise NotImplementedError
        self.setCurrentIndex(index)

    def _update_header(self) -> None:
        label = self.default_view.header_label
        if STATE.current_file is None:
            label.setText("No document")

        elif STATE.scan_state == ScanState.IN_PROGRESS:
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
