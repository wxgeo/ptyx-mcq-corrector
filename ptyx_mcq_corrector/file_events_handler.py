from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Final, Sequence, Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog, QDialogButtonBox
from ptyx_mcq.cli import get_template_path, update as update_include

import ptyx_mcq_corrector.param as param
from ptyx_mcq_corrector.internal_state import State

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
    file_missing = pyqtSignal(str, name="file_missing")

    def __init__(self, main_window: "McqCorrectorMainWindow"):
        super().__init__(parent=main_window)
        self.main_window: Final = main_window
        self.freeze_update_ui: bool = False  # See update_ui() decorator docstring.
        self.file_missing.connect(self.create_missing_file)

    @update_ui
    def finalize(self, paths: Sequence[Path] = ()) -> bool:
        if paths:
            self.state.new_session()
            self.open_dir(paths=paths)
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

        if (current_dir := self.state.current_dir) is not None:
            self.main_window.setWindowTitle(f"{param.WINDOW_TITLE} - {current_dir.name}")
        else:
            self.main_window.setWindowTitle(param.WINDOW_TITLE)
        self.update_status_message()

    @update_ui
    def open_dir(self, path: Path = None) -> bool:
        if path is None:
            path = self.open_dir_dialog()
            if path is None:
                return False
        if not (path.is_dir()):
            raise FileNotFoundError(f"Directory '{path}' does not exist.")
        elif self.state.current_dir is not None and path.resolve() == self.state.current_dir:
            print(f"Directory '{path.name}' already opened.")
        return self.state.open_dir(path)

    @update_ui
    def close_dir(self) -> bool:
        """Close current directory."""
        self.state.close_doc()
        return True

    # -----------------
    #      Dialogs
    # =================

    def open_dir_dialog(self) -> Path | None:
        # noinspection PyTypeChecker
        dirname = QFileDialog.getExistingDirectory(
            self.main_window,
            "Open pTyX directory",
            str(self.state.current_dir),
        )
        return Path(dirname) if dirname else None

    def update_status_message(self) -> None:
        # TODO: implement status message.
        self.main_window.statusbar.setStyleSheet("")
        self.main_window.status_label.setText("")
