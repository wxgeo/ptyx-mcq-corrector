import threading
from functools import wraps
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, Final, Callable

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox, QFileDialog

import ptyx_mcq_corrector.param as param
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq_corrector.internal_state import ScanState
from ptyx_mcq_corrector.issues.issues_model import IssueInfo, IssueType
from ptyx_mcq_corrector.review.checkboxes import CheckboxesReviewer
from ptyx_mcq_corrector.review.name import NameReviewer, student_to_text, student_from_text, NameStatus

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

StandardButton = QMessageBox.StandardButton
# Abort = QMessageBox.StandardButton.Abort
# Discard = QMessageBox.StandardButton.Discard
# Save = QMessageBox.StandardButton.Save


FILES_FILTER = (
    "All supported Files (*.ex *.ptyx)",
    "Mcq Exercises Files (*.ex)",
    "pTyX Files (*.ptyx)",
    "All Files (*.*)",
)


def update_ui(f: Callable[..., bool]) -> Callable[..., bool]:
    """Decorator used to indicate that UI must be updated if the operation was successful.

    The decorated function must return True if the operation was successful, False else.

    When nested operations are performed, intermediate ui updates are prevented by
    freezing temporally the user interface, then updating it only once the last operation is performed.
    """

    @wraps(f)
    def wrapper(self: "FileEventsHandler", *args, **kw) -> bool:
        current_freeze_value = self.freeze_update_ui
        self.freeze_update_ui = True
        if not param.DEBUG:
            self.main_window.setUpdatesEnabled(False)
        try:
            if param.DEBUG:
                _args = [repr(arg) for arg in args] + [f"{key}={val!r}" for (key, val) in kw.items()]
                print(f"{f.__name__}({', '.join(_args)})")
            else:
                print(f.__name__)
            update = f(self, *args, **kw)
            assert isinstance(update, bool), (
                f"Method `FileEventsHandler.{f.__name__}` must return a boolean, not {update!r}"
            )
            if update and not current_freeze_value:
                self._update_ui()
            return update
        finally:
            self.main_window.setUpdatesEnabled(True)
            self.freeze_update_ui = current_freeze_value

    return wrapper


class FileEventsHandler(QObject):
    def __init__(self, main_window: "McqCorrectorMainWindow"):
        super().__init__(parent=main_window)
        self.main_window: Final = main_window
        self.freeze_update_ui: bool = False  # See update_ui() decorator docstring.
        self.abort_event = threading.Event()

    @update_ui
    def finalize(self, path: Path | None = None) -> bool:
        if path is not None:
            self.open_file(path)
        return True

    def scan_or_abort(self) -> None:
        if self.state.scan_state == ScanState.IN_PROGRESS:
            self.abort()
        else:
            self.scan()

    def abort(self) -> None:
        """Call this slot to abort the current running action, if possible."""
        self.abort_event.set()

    def scan(self) -> None:
        self.main_window.scan_requested.emit()

    def _name_suggestions(self) -> list[str]:
        return sorted([student_to_text(student) for student in self.state.students])

    def on_name_changed(self, text: str) -> None:
        if text in self._name_suggestions():
            assert isinstance(reviewer := self.main_window.current_reviewer, NameReviewer)
            reviewer.page.pic.student = student_from_text(text)
            self.main_window.name_editor.display_as(NameStatus.VALID)
        else:
            self.main_window.name_editor.display_as(NameStatus.INVALID)

    @update_ui
    def validate_issue(self) -> bool:
        if (issue := self.state.current_issue) is None:
            return False
        if (model := self.main_window.issuesView.model()) is None:
            return False
        self.main_window.checkboxes_review.validate()
        model.validate(issue.index)
        self.main_window.issuesView.move_to_next_index()
        return True

    # ---------------------
    #      Shortcuts
    # =====================

    @property
    def state(self):
        return self.main_window.state

    # ------------------------------------------
    #      UI synchronization with state
    # ==========================================

    def _update_ui(self) -> None:
        """Update window and tab titles according to state data.

        Assure synchronization between ui and state."""
        self.main_window.update_ui()

    # -------------------------------
    #    Functions for each state
    # ===============================

    # def action_none(self):
    #     self.main_window.disable_navigation()
    #
    # def action_integrity_request(self):
    #     print("Integrity request.")
    #
    # def action_name_request(self):
    #     pass
    #
    # def action_answers_request(self):
    #     pass
    #
    # def action_results(self):
    #     pass

    # --------------------------
    #    Events affecting UI
    # ==========================

    @update_ui
    def on_issue_selected(self, issue: IssueInfo) -> bool:
        assert issue is not None
        self.state.current_issue = issue  # To do at first!
        doc = self.state.parser.scan_data.used_docs_index[issue.doc]
        # Be careful to select the reviewer only *AFTER* the state have been changed.
        reviewer = self.main_window.current_reviewer
        match issue.type:
            case IssueType.NAMES:
                assert isinstance(reviewer, NameReviewer)
                reviewer.page = doc.first_page
                # Update suggestions
                self.main_window.name_editor.set_suggestions(self._name_suggestions())
                self.main_window.name_editor.set_current_student(reviewer.page.pic.student)
            case IssueType.AMBIGUOUS_ANSWERS:
                assert isinstance(reviewer, CheckboxesReviewer)
                page = doc.pages_index[issue.page]
                reviewer.page = page
        assert reviewer is not None
        reviewer.setFocus()
        return True

    @update_ui
    def reset(self) -> bool:
        """Reset scan data."""
        # Ask for confirmation.
        if (
            QMessageBox.question(
                self.main_window,
                "Remove previous scan data",
                "Are you sure you want to remove any existing scan data?",
                StandardButton.Yes | StandardButton.Cancel,
                StandardButton.Cancel,
            )
            == StandardButton.Yes
        ):
            self.state.scan_state = ScanState.TO_DO
            # rmtree(folder := (self.state.current_file.parent / "out"))
            self.state.parser.scan_data.reset()
            print(f"Folder '{self.state.current_file.parent / 'out'}' was removed.")
            return True
        return False

    @update_ui
    def open_file(self, path: Path | None = None) -> bool:
        if path is None:
            path = self.open_file_dialog()
            print(f"Selected path: '{path}'.")
            if path is None:
                return False
        return self.state.open_file(path)

    @update_ui
    def close_file(self) -> bool:
        """Close current directory."""
        self.state.close_file()
        return True

    @update_ui
    def start_scan(self) -> bool:
        """Launch scan."""
        print(f"Starting scan of '{self.state.current_file}'...")
        return True

    # @update_ui
    # def on_request(self, request: McqRequest) -> bool:
    #     """Handle requests from the scan process."""
    #     assert isinstance(request, McqRequest), f"Invalid request: {request!r}"
    #     self.state.current_action = Action.PENDING_REQUEST
    #     self.state.current_request = request
    #     return True

    @update_ui
    def on_scan_started(self) -> bool:
        self.state.current_issue = None
        self.state.scan_state = ScanState.IN_PROGRESS
        msg = f"Starting scan of '{self.state.current_file}'..."
        print(msg)
        self.main_window.header_label.setText(msg)
        return True

    def on_scan_in_progress(self, msg: str = "Work in progress..."):
        self.main_window.header_label.setText(msg)

    @update_ui
    def on_scan_ended(self) -> bool:
        self.state.scan_state = ScanState.DONE
        self.main_window.issuesView.display_issues()
        return True

    @update_ui
    def on_scan_aborted(self) -> bool:
        self.abort_event.clear()
        self.state.scan_state = ScanState.TO_DO
        print("Scan aborted.")
        return True

    # -----------------
    #      Dialogs
    # =================

    def open_file_dialog(self) -> Path | None:
        # noinspection PyTypeChecker
        filename, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Open pTyX MCQ configuration file",
            str(self.state.current_file),
            f"pTyX MCQ configuration file (*{CONFIG_FILE_EXTENSION})",
        )
        return Path(filename) if filename else None
