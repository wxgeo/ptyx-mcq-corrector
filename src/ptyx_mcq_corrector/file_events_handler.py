import threading
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION
from ptyx_mcq_corrector.app_state import STATE, State
from ptyx_mcq_corrector.tools import update_ui
from ptyx_mcq_corrector.views.main_area import DEFAULTS_VIEW_MODES

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

StandardButton = QMessageBox.StandardButton
# Abort = QMessageBox.StandardButton.Abort
# Discard = QMessageBox.StandardButton.Discard
# Save = QMessageBox.StandardButton.Save


class ResetMode(StrEnum):
    SCAN = "scan"
    REVIEW = "integrity_issues"


class FileEventsHandler(QObject):
    def __init__(self, main_window: "McqCorrectorMainWindow"):
        super().__init__(parent=main_window)
        self.main_window: Final = main_window
        self.abort_event = threading.Event()

    @update_ui
    def finalize(self, path: Path | None = None) -> bool:
        if path is not None:
            self.open_file(path)
        return True

    def scan_or_abort(self) -> None:
        if STATE.state == State.SCAN_IN_PROGRESS:
            self.abort()
        else:
            self.scan()

    def abort(self) -> None:
        """Call this slot to abort the current running action, if possible."""
        self.abort_event.set()

    def scan(self) -> None:
        self.main_window.scan_requested.emit()

    # --------------------------
    #    Events affecting UI
    # ==========================

    @property
    def state(self) -> State:
        return STATE.state

    @update_ui
    def update_state(self, state: State) -> bool:
        """Set the application global state and update the view accordingly."""
        if STATE.state == state:
            return False
        STATE.state = state  # To do at first!
        view_mode = DEFAULTS_VIEW_MODES[state]
        self.main_window.main_area.view_mode = view_mode
        return True

    @update_ui
    def reset(self, reset_mode: ResetMode) -> bool:
        """Reset scan/integrity_issues data."""
        # Ask for confirmation.
        if (
            QMessageBox.question(
                self.main_window,
                f"Remove previous {reset_mode} data",
                f"Are you sure you want to remove any existing {reset_mode} data?",
                StandardButton.Yes | StandardButton.Cancel,
                StandardButton.Cancel,
            )
            == StandardButton.Yes
        ):
            self.update_state(State.NO_SCAN)
            # rmtree(folder := (self.state.current_file.parent / "out"))
            parser = STATE.parser
            current_file = STATE.current_file
            assert parser is not None
            assert current_file is not None
            if reset_mode == ResetMode.SCAN:
                parser.scan_data.reset()
                print(f"Folder '{current_file.parent / 'out'}' was removed.")
            elif reset_mode == ResetMode.REVIEW:
                parser.scan_data.reset_review()
                print(f"Folder '{current_file.parent / 'out/.fix'}' was removed.")
            return True
        return False

    @update_ui
    def open_file(self, path: Path | None = None) -> bool:
        if path is None:
            path = self.open_file_dialog()
            print(f"Selected path: '{path}'.")
            if path is None:
                return False
        return STATE.open_file(path)

    @update_ui
    def close_file(self) -> bool:
        """Close current directory."""
        STATE.close_file()
        return True

    @update_ui
    def start_scan(self) -> bool:
        """Launch scan."""
        print(f"Starting scan of '{STATE.current_file}'...")
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
        STATE.current_issue = None
        self.update_state(State.SCAN_IN_PROGRESS)
        return True

    def on_scan_in_progress(self, msg: str = "Work in progress..."):
        self.main_window.main_area.default_view.header_label.setText(msg)

    @update_ui
    def on_scan_ended(self) -> bool:
        if STATE.integrity_issues_detected:
            self.update_state(State.INTEGRITY_ISSUES)
        elif STATE.data_issues_detected:
            self.update_state(State.DATA_ISSUES)
            self.main_window.main_area.data_view.update_issues()
        else:
            self.update_state(State.VALIDATED)
        return True

    @update_ui
    def on_scan_aborted(self) -> bool:
        self.abort_event.clear()
        self.update_state(State.NO_SCAN)
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
            str(STATE.current_file),
            f"pTyX MCQ configuration file (*{CONFIG_FILE_EXTENSION})",
        )
        return Path(filename) if filename else None
