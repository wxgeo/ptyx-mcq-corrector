import threading
from functools import wraps
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, Final, Callable

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QFileDialog

import ptyx_mcq_corrector.param as param
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq_corrector.internal_state import ScanState
from ptyx_mcq_corrector.issues.issues_model import IssueInfo

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

    def abort(self) -> None:
        """Call this slot to abort the current running action, if possible."""
        self.abort_event.set()

    # ---------------------
    #      Shortcuts
    # =====================

    @property
    def state(self):
        return self.main_window.state

    # ------------------------------------------
    #      UI synchronization with state
    # ==========================================

    @property
    def current_file_shortname(self) -> str:
        return (
            self.state.current_file.name[: -len(CONFIG_FILE_EXTENSION)]
            if self.state.current_file is not None
            else ""
        )

    def _update_ui(self) -> None:
        """Update window and tab titles according to state data.

        Assure synchronization between ui and state."""
        self.main_window.main_area.setCurrentIndex(0)
        self.main_window.disable_review_ui()

        if self.state.current_file is None:
            self.main_window.setWindowTitle(param.WINDOW_TITLE)
            self.main_window.header_label.setText("No document")
            self.main_window.action_button.hide()
            return

        name = self.current_file_shortname
        self.main_window.setWindowTitle(f"{param.WINDOW_TITLE} - {name}")
        # Any non-null value is OK for `href`, but it can't be left empty, else Qt doesn't generate a link at all.
        self.main_window.header_label.setText(
            f"<p style='text-align:center'>Document <i><b><a href='#'>{name}</a></b></i> selected.</p>"
            "<p style='text-align:center;font-size:small'>Press <b>F5</b> to start scanning.</p>"
        )
        try:
            self.main_window.header_label.linkActivated.disconnect()
        except TypeError:
            pass  # no connection existed yet
        self.main_window.header_label.linkActivated.connect(
            lambda _: self.main_window.file_events_handler.open_file()
        )
        self.main_window.header_label.setOpenExternalLinks(False)
        action_button = self.main_window.action_button
        try:
            action_button.clicked.disconnect()
        except TypeError:
            pass  # no connection existed yet
        self.main_window.actionScan_documents.setEnabled(True)

        if self.state.scan_state == ScanState.TO_DO:
            action_button.setText("Scan")
            action_button.setIcon(QIcon.fromTheme("media-playback-start"))
            action_button.show()
            action_button.clicked.connect(self.main_window.scan_handler.scan)
        elif self.state.scan_state == ScanState.IN_PROGRESS:
            action_button.setText("Abort")
            action_button.setIcon(QIcon.fromTheme("process-stop"))
            action_button.clicked.connect(self.abort)
            self.main_window.actionScan_documents.setEnabled(False)
        elif self.state.scan_state == ScanState.DONE:
            self.main_window.enable_review_ui()

        self.update_status_message()  # TODO

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
        self.state.current_issue = issue
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
            rmtree(folder := (self.state.current_file.parent / "out"))
            self.state.parser.scan_data.reset()
            print(f"Folder '{folder}' was removed.")
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

    def update_status_message(self) -> None:
        # TODO: implement status message.
        self.main_window.statusbar.setStyleSheet("")
        self.main_window.status_label.setText("")
