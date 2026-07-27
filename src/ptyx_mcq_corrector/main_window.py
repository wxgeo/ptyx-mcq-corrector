#!/usr/bin/python3
from argparse import Namespace
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QLabel, QMainWindow, QWidget

from ptyx_mcq_corrector import param
from ptyx_mcq_corrector.about import AboutDialog
from ptyx_mcq_corrector.file_events_handler import FileEventsHandler
from ptyx_mcq_corrector.generated_ui.main_ui import Ui_MainWindow
from ptyx_mcq_corrector.internal_state import State, ScanState
from ptyx_mcq_corrector.issues.issues_model import IssuesModel, IssueType
from ptyx_mcq_corrector.param import ICON_PATH
from ptyx_mcq_corrector.review.abstract_reviewer import PixReviewer
from ptyx_mcq_corrector.scan.scan_manager import ScanManager


def path_hash(path: Path | str) -> str:
    return urlsafe_b64encode(hash(str(path)).to_bytes(8, signed=True)).decode("ascii").rstrip("=")


@dataclass
class ReviewerInfo:
    index: int
    reviewer: QWidget


class McqCorrectorMainWindow(QMainWindow, Ui_MainWindow):
    # restore_session_signal = pyqtSignal(name="restore_session_signal")
    # new_session_signal = pyqtSignal(name="new_session_signal")

    scan_requested = pyqtSignal(name="scan_requested")

    def __init__(self, args: Namespace) -> None:
        super().__init__(parent=None)
        # Always load state, even when opening a new session,
        # to get at least the recent files list.
        self.state = State.load()
        self.file_events_handler = FileEventsHandler(self)
        self.setupUi(self)

        # Management of the scan processes takes place in another thread, to keep the UI responsive.
        self.scan_handler = ScanManager(self)
        self.scan_thread = QThread(self)
        self.scan_handler.moveToThread(self.scan_thread)

        self.issuesView.setModel(IssuesModel(self.state))

        # List all the different issues reviewers, with their index in their QStackedWidget parent.
        self._issues_reviewers: dict[IssueType, ReviewerInfo] = {
            IssueType.NAMES: ReviewerInfo(1, self.name_review),
            IssueType.AMBIGUOUS_ANSWERS: ReviewerInfo(2, self.checkboxes_review),
        }

        # -----------------
        # Customize display
        # -----------------
        if not ICON_PATH.is_file():
            print(f"File not found: {ICON_PATH}")
        else:
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.status_label = QLabel(self)
        self.statusbar.addWidget(self.status_label)

        # -------------------
        #   Connect signals
        # -------------------
        self.connect_menu_signals()
        self.file_events_handler.finalize(args.path)
        self.scan_thread.start()
        self.scan_requested.connect(self.scan_handler.scan)
        self.scan_handler.scan_progress.connect(self.file_events_handler.on_scan_in_progress)
        for reviewer_info in self._issues_reviewers.values():
            if isinstance(reviewer := reviewer_info.reviewer, PixReviewer):
                reviewer.previous_page_requested.connect(self.issuesView.move_to_previous_index)
                reviewer.next_page_requested.connect(self.issuesView.move_to_next_index)
                reviewer.esc_requested.connect(self.issuesView.setFocus)

        print("PARENT:", self.dockWidgetContents.parent())

    def connect_menu_signals(self) -> None:
        # Don't change handler variable value (because of name binding process in lambdas).
        handler: Final[FileEventsHandler] = self.file_events_handler

        # *** 'File' menu ***
        self.action_Open_directory.triggered.connect(lambda: handler.open_file())
        # Don't use lambda, else the thread will not be detected correctly by Qt.
        self.actionScan_documents.triggered.connect(self.file_events_handler.scan_or_abort)
        self.action_Reset_scan.triggered.connect(lambda: handler.reset())

        self.actionNext.triggered.connect(self.issuesView.move_to_next_index)
        self.actionPrevious.triggered.connect(self.issuesView.move_to_previous_index)
        self.actionValidate.triggered.connect(lambda: self.file_events_handler.validate_issue())

        self.action_Close.triggered.connect(lambda: handler.close_file())
        self.menu_File.aboutToShow.connect(self._update_recent_files_menu)
        self.action_About.triggered.connect(self.about)

    # noinspection PyMethodOverriding
    def closeEvent(self, event: QCloseEvent | None) -> None:
        assert event is not None
        assert self is not None
        if self.request_to_close():
            self.file_events_handler.abort()
            self.scan_thread.quit()
            self.scan_thread.wait()
            event.accept()
        else:
            event.ignore()

    def update_ui(self) -> None:
        self.main_area.setCurrentIndex(0)
        self._update_review_ui()
        self._update_scan_ui()
        self._update_title()
        self._update_header()
        self._update_main_area()
        self._update_status_message()  # TODO

    @property
    def current_reviewer(self) -> QWidget | None:
        if (issue := self.state.current_issue) is None:
            return None
        return self._issues_reviewers[issue.type].reviewer

    def _update_main_area(self) -> None:
        if (issue := self.state.current_issue) is None:
            index = 0
        else:
            index = self._issues_reviewers[issue.type].index
        self.main_area.setCurrentIndex(index)

    def _update_scan_ui(self) -> None:
        action = self.actionScan_documents
        if self.state.scan_state == ScanState.IN_PROGRESS:
            text = "&Abort scan"
            mime = "process-stop"
        else:
            text = "&Scan documents"
            mime = "scanner"
        action.setText(text)
        action.setIcon(QIcon.fromTheme(mime))
        action.setEnabled(self.state.current_file is not None)
        self.action_Reset_scan.setEnabled(
            self.state.current_file is not None and self.state.scan_state != ScanState.IN_PROGRESS
        )

    def _update_title(self) -> None:
        title = param.WINDOW_TITLE
        if self.state.current_file is not None:
            title += f" - {self.state.current_file_shortname}"
        self.setWindowTitle(title)

    def _update_header(self) -> None:
        if self.state.current_file is None:
            self.header_label.setText("No document")
        else:
            self.header_label.setText(self.state.current_file_shortname)
            # Any non-null value is OK for `href`, but it can't be left empty, else Qt doesn't generate a link at all.
            self.header_label.setText(
                "<p style='text-align:center'>Document <i><b>"
                f"<a href='#'>{self.state.current_file_shortname}</a>"
                "</b></i> selected.</p>"
                "<p style='text-align:center;font-size:small'>Press <b>F5</b> to start scanning.</p>"
            )
            try:
                self.header_label.linkActivated.disconnect()
            except TypeError:
                pass  # no connection existed yet
            self.header_label.linkActivated.connect(lambda _: self.file_events_handler.open_file())
            self.header_label.setOpenExternalLinks(False)

    def _disable_review_ui(self):
        self.menuReview.setEnabled(False)
        self.issuesDock.hide()
        for action in [self.actionPrevious, self.actionNext, self.actionValidate]:
            action.setVisible(False)

    def _enable_review_ui(self):
        for action in [self.actionPrevious, self.actionNext, self.actionValidate]:
            action.setVisible(True)
            action.setEnabled(self.state.current_issue is not None)
        self.menuReview.setEnabled(True)
        model = self.issuesView.model()
        assert isinstance(model, IssuesModel)
        self.issuesDock.setWindowTitle(model.title)
        self.issuesDock.show()

    def _update_review_ui(self) -> None:
        if self.state.scan_state == ScanState.DONE:
            self._enable_review_ui()
        else:
            self._disable_review_ui()

    def request_to_close(self) -> bool:
        """Save state and return a boolean indicating if closing is accepted.

        For now, requests are always accepted."""
        self.state.save()
        return True

    # noinspection PyDefaultArgument
    def _update_recent_files_menu(self) -> None:
        recent_files = tuple(self.state.recent_files)
        if not recent_files:
            self.menu_Recent_files.menuAction().setVisible(False)
        else:
            self.menu_Recent_files.clear()
            for recent_file in recent_files:
                action = self.menu_Recent_files.addAction(recent_file.name)
                # This is tricky.
                # 1. Function provided must not use `recent_file` as unbound variable,
                # since its value will change later in this loop.
                # So, we use a default argument as a trick to copy current `recent_file` value
                # (and not a reference) inside the function.
                # 2. PyQt pass to given slot a boolean value (what is its meaning ??) if (and only if)
                # it detects that the function have at least one argument.
                # So, we have to provide a first dummy argument to the following lambda function.
                action.triggered.connect(
                    lambda _, path=recent_file: self.file_events_handler.open_file(path=path)
                )
            self.menu_Recent_files.menuAction().setVisible(True)

    def _update_status_message(self) -> None:
        # TODO: implement status message.
        self.statusbar.setStyleSheet("")
        self.status_label.setText("")

    def add_desktop_menu_entry(self) -> None:
        pass

    def about(self) -> None:
        AboutDialog(self).exec()
