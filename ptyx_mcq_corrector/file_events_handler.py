from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Final, Sequence, Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog, QDialogButtonBox
from ptyx_mcq.cli import get_template_path, update as update_include
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION

import ptyx_mcq_corrector.param as param
from ptyx_mcq_corrector.internal_state import State, Action

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

Abort = QMessageBox.StandardButton.Abort
Discard = QMessageBox.StandardButton.Discard
Save = QMessageBox.StandardButton.Save

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
            assert isinstance(
                update, bool
            ), f"Method `FileEventsHandler.{f.__name__}` must return a boolean, not {update!r}"
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

    @update_ui
    def finalize(self, path: Path = None) -> bool:
        if path is not None:
            self.open_file(path)
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

        if self.state.current_file is None:
            self.main_window.setWindowTitle(param.WINDOW_TITLE)
            self.main_window.header_label.setText("No document")
        else:
            name = self.current_file_shortname
            self.main_window.setWindowTitle(f"{param.WINDOW_TITLE} - {name}")
            self.main_window.header_label.setText(
                f"<p style='text-align:center'>Document <i><b>{name}</b></i> selected.</p>"
                "<p style='text-align:center;font-size:small'>Press <b>F5</b> to start scanning.</p>"
            )
            self.main_window.enable_navigation()

        match self.state.current_action:
            case Action.NONE:
                self.action_none()

        self.update_status_message()

    # -------------------------------
    #    Functions for each state
    # ===============================

    def action_none(self):
        self.main_window.disable_navigation()

    # --------------------------
    #    Events affecting UI
    # ==========================

    @update_ui
    def open_file(self, path: Path = None) -> bool:
        if path is None:
            path = self.open_file_dialog()
            print(f"Selected path: '{path}'.")
            if path is None:
                return False
        return self.state.open_file(path)

    @update_ui
    def close_file(self) -> bool:
        """Close current directory."""
        self.state.close_doc()
        return True

    @update_ui
    def start_scan(self) -> bool:
        """Launch scan."""
        print(f"Starting scan of '{self.state.current_file}'...")
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
