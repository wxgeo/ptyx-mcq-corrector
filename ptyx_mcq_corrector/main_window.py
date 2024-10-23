#!/usr/bin/python3
from argparse import Namespace
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Final

from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QMainWindow, QLabel

from ptyx_mcq_corrector.file_events_handler import FileEventsHandler
from ptyx_mcq_corrector.generated_ui.main_ui import Ui_MainWindow
from ptyx_mcq_corrector.internal_state import State
from ptyx_mcq_corrector.param import ICON_PATH
from ptyx_mcq_corrector.scan.scan_handler import ScannerManager


def path_hash(path: Path | str) -> str:
    return urlsafe_b64encode(hash(str(path)).to_bytes(8, signed=True)).decode("ascii").rstrip("=")


class McqCorrectorMainWindow(QMainWindow, Ui_MainWindow):
    # restore_session_signal = pyqtSignal(name="restore_session_signal")
    # new_session_signal = pyqtSignal(name="new_session_signal")

    def __init__(self, args: Namespace = None) -> None:
        super().__init__(parent=None)
        # Always load state, even when opening a new session,
        # to get at least the recent files list.
        self.state = State.load()
        self.file_events_handler = FileEventsHandler(self)
        self.scan_handler = ScannerManager(self)
        self.setupUi(self)

        # self.tmp_dir = Path(mkdtemp(prefix="mcq-editor-"))
        # print("created temporary directory", self.tmp_dir)

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

    def connect_menu_signals(self) -> None:
        # Don't change handler variable value (because of name binding process in lambdas).
        handler: Final[FileEventsHandler] = self.file_events_handler

        # *** 'File' menu ***
        self.action_Open_directory.triggered.connect(lambda: handler.open_file())
        self.actionScan_documents.triggered.connect(lambda: self.scan_handler.launch_scan())
        # self.action_Save.triggered.connect(lambda: handler.save_doc(side=None, index=None))
        # self.actionSave_as.triggered.connect(lambda: handler.save_doc_as(side=None, index=None))
        # self.action_Close.triggered.connect(lambda: handler.close_doc(side=None, index=None))
        # self.actionN_ew_Session.triggered.connect(lambda: handler.new_session())
        # self.menuFichier.aboutToShow.connect(self.update_recent_files_menu)
        #
        # # *** 'Make' menu ***
        # self.action_LaTeX.triggered.connect(lambda: self.compilation_tabs.generate_latex())
        # self.action_Pdf.triggered.connect(lambda: self.compilation_tabs.generate_pdf())
        # # Support multiple shortcuts
        # self.action_Pdf.setShortcuts(["F5", "Ctrl+Return"])
        # self.action_LaTeX.setShortcuts(["Shift+F5", "Ctrl+Shift+Return"])
        # self.actionPublish.triggered.connect(
        #     lambda: self.publish_toolbar.setVisible(not self.publish_toolbar.isVisible())
        # )
        #
        # # *** 'Code' menu ***
        # self.action_Update_imports.triggered.connect(handler.update_ptyx_imports)
        # self.action_Add_folder.triggered.connect(handler.add_directory)
        # self.action_Open_file_from_current_import_line.triggered.connect(
        #     lambda: handler.open_file_from_current_ptyx_import_directive()
        # )
        # self.actionComment.triggered.connect(handler.toggle_comment)
        # self.actionFormat_python_code.triggered.connect(handler.format_file)
        #
        # # *** 'Tools' menu ***
        # self.action_Add_MCQ_Editor_to_start_menu.triggered.connect(self.add_desktop_menu_entry)
        #
        # # *** 'Edit' menu ***
        # self.actionFind.triggered.connect(
        #     lambda: self.search_dock.toggle_find_and_replace_dialog(replace=False)
        # )
        # self.actionReplace.triggered.connect(
        #     lambda: self.search_dock.toggle_find_and_replace_dialog(replace=True)
        # )
        #
        # # *** 'Debug' menu ***
        # self.action_Send_Qscintilla_Command.triggered.connect(self.dbg_send_scintilla_command)

    # noinspection PyMethodOverriding
    def closeEvent(self, event: QCloseEvent | None) -> None:
        assert event is not None
        assert self is not None
        if self.request_to_close():
            event.accept()
        else:
            event.ignore()

    def disable_navigation(self):
        self.previous_button.hide()
        self.next_button.hide()

    def enable_navigation(self):
        self.previous_button.show()
        self.next_button.show()

    def request_to_close(self) -> bool:
        """Save state and return a boolean indicating if closing is accepted.

        For now, requests are always accepted."""
        self.state.save()
        return True

    # noinspection PyDefaultArgument
    def update_recent_files_menu(self) -> None:
        recent_files = tuple(self.state.recent_files)
        if not recent_files:
            self.menu_Recent_Files.menuAction().setVisible(False)
        else:
            self.menu_Recent_Files.clear()
            for recent_file in recent_files:
                action = self.menu_Recent_Files.addAction(recent_file.name)
                # This is tricky.
                # 1. Function provided must not use `recent_file` as unbound variable,
                # since its value will change later in this loop.
                # So, we use a default argument as a trick to copy current `recent_file` value
                # (and not a reference) inside the function.
                # 2. PyQt pass to given slot a boolean value (what is its meaning ??) if (and only if)
                # it detects that the function have at least one argument.
                # So, we have to provide a first dummy argument to the following lambda function.
                action.triggered.connect(
                    lambda _, paths=[recent_file]: self.file_events_handler.open_doc(
                        side=None, paths=list(paths)
                    )
                )
            self.menu_Recent_Files.menuAction().setVisible(True)

    def add_desktop_menu_entry(self) -> None:
        pass
        # completed_process = install_desktop_shortcut()
        # if completed_process.returncode == 0:
        #     # noinspection PyTypeChecker
        #     QMessageBox.information(
        #         self, "Shortcut installed", "This application was successfully added to start menu."
        #     )
        # else:
        #     # noinspection PyTypeChecker
        #     QMessageBox.critical(self, "Unable to install shortcut", completed_process.stdout)

    # def get_temp_path(self, suffix: Literal["tex", "pdf"], doc_path: Path = None) -> Path | None:
    #     """Get the path of a temporary file corresponding to the current document."""
    #     if doc_path is None:
    #         doc = self.state.current_doc
    #         if doc is None:
    #             return None
    #         doc_path = doc.path
    #         if doc_path is None:
    #             doc_path = Path(f"new-doc-{doc.doc_id}")
    #     return self.tmp_dir / f"{'' if doc_path is None else doc_path.stem}-{path_hash(doc_path)}.{suffix}"
