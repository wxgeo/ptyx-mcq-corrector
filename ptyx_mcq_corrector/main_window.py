#!/usr/bin/python3
import shutil
from argparse import Namespace
from base64 import urlsafe_b64encode
from pathlib import Path
from tempfile import mkdtemp
from typing import Final, Literal

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QLabel

from ptyx_mcq_editor.editor.editor_widget import EditorWidget
from ptyx_mcq_editor.events_handler import FileEventsHandler
from ptyx_mcq_editor.generated_ui.main_ui import Ui_MainWindow
from ptyx_mcq_editor.param import ICON_PATH
from ptyx_mcq_editor.settings import Settings, Side
from ptyx_mcq_editor.tools import install_desktop_shortcut


def path_hash(path: Path | str) -> str:
    return urlsafe_b64encode(hash(str(path)).to_bytes(8, signed=True)).decode("ascii").rstrip("=")


class McqEditorMainWindow(QMainWindow, Ui_MainWindow):
    # restore_session_signal = pyqtSignal(name="restore_session_signal")
    # new_session_signal = pyqtSignal(name="new_session_signal")

    def __init__(self, args: Namespace = None) -> None:
        super().__init__(parent=None)
        # Always load settings, even when opening a new session,
        # to get at least the recent files list.
        self.settings = Settings.load_settings()
        self.file_events_handler = FileEventsHandler(self)
        self.setupUi(self)
        self.books = {Side.LEFT: self.left_tab_widget, Side.RIGHT: self.right_tab_widget}
        for side, book in self.books.items():
            book.finish_initialization(side=side)

        # -----------------
        # Internal settings
        # -----------------
        self.tmp_dir = Path(mkdtemp(prefix="mcq-editor-"))
        print("created temporary directory", self.tmp_dir)
        # self.ui_updates_enabled = True

        # -----------------
        # Customize display
        # -----------------
        if not ICON_PATH.is_file():
            print(f"File not found: {ICON_PATH}")
        else:
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.search_dock.setVisible(False)
        # self.publish_dock.setVisible(False)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

        # TODO: enable right view
        self.hide_right_view()

        self.status_label = QLabel(self)
        self.statusbar.addWidget(self.status_label)

        # self.publish_toolbar = PublishToolBar(self)
        # self.addToolBar(self.publish_toolbar)

        # self.publish_toolbar.addWidget(PublishWidget(self))
        self.publish_toolbar.hide()

        # -------------------
        #   Connect signals
        # -------------------
        self.connect_menu_signals()
        self.search_dock.connect_signals()

        self.file_events_handler.finalize([Path(path) for path in args.paths] if args is not None else [])

    def connect_menu_signals(self) -> None:
        # Don't change handler variable value (because of name binding process in lambdas).
        handler: Final[FileEventsHandler] = self.file_events_handler

        # *** 'File' menu ***
        self.action_Empty_file.triggered.connect(lambda: handler.new_doc(side=None, content=None))
        self.action_Mcq_ptyx_file.triggered.connect(lambda: handler.new_mcq_ptyx_doc(side=None))
        self.action_Open.triggered.connect(lambda: handler.open_doc(side=None))
        self.action_Save.triggered.connect(lambda: handler.save_doc(side=None, index=None))
        self.actionSave_as.triggered.connect(lambda: handler.save_doc_as(side=None, index=None))
        self.action_Close.triggered.connect(lambda: handler.close_doc(side=None, index=None))
        self.actionN_ew_Session.triggered.connect(lambda: handler.new_session())
        self.menuFichier.aboutToShow.connect(self.update_recent_files_menu)

        # *** 'Make' menu ***
        self.action_LaTeX.triggered.connect(lambda: self.compilation_tabs.generate_latex())
        self.action_Pdf.triggered.connect(lambda: self.compilation_tabs.generate_pdf())
        # Support multiple shortcuts
        self.action_Pdf.setShortcuts(["F5", "Ctrl+Return"])
        self.action_LaTeX.setShortcuts(["Shift+F5", "Ctrl+Shift+Return"])
        self.actionPublish.triggered.connect(
            lambda: self.publish_toolbar.setVisible(not self.publish_toolbar.isVisible())
        )

        # *** 'Code' menu ***
        self.action_Update_imports.triggered.connect(handler.update_ptyx_imports)
        self.action_Add_folder.triggered.connect(handler.add_directory)
        self.action_Open_file_from_current_import_line.triggered.connect(
            lambda: handler.open_file_from_current_ptyx_import_directive()
        )
        self.actionComment.triggered.connect(handler.toggle_comment)
        self.actionFormat_python_code.triggered.connect(handler.format_file)

        # *** 'Tools' menu ***
        self.action_Add_MCQ_Editor_to_start_menu.triggered.connect(self.add_desktop_menu_entry)

        # *** 'Edit' menu ***
        self.actionFind.triggered.connect(
            lambda: self.search_dock.toggle_find_and_replace_dialog(replace=False)
        )
        self.actionReplace.triggered.connect(
            lambda: self.search_dock.toggle_find_and_replace_dialog(replace=True)
        )

        # *** 'Debug' menu ***
        self.action_Send_Qscintilla_Command.triggered.connect(self.dbg_send_scintilla_command)

    # noinspection PyMethodOverriding
    def closeEvent(self, event: QCloseEvent | None) -> None:
        assert event is not None
        assert self is not None
        if self.request_to_close():
            event.accept()
        else:
            event.ignore()

    @property
    def current_mcq_editor(self) -> EditorWidget | None:
        side = self.settings.current_side
        current_book = self.books[side]
        current_tab = current_book.currentWidget()
        return None if current_tab is None else current_tab.editor

    def hide_right_view(self) -> None:
        self.right_tab_widget.hide()

    def request_to_close(self) -> bool:
        if self.file_events_handler.ask_for_saving_if_needed():
            self.settings.save_settings()
            shutil.rmtree(self.tmp_dir)
            # Pdf doc must be closed to avoid a segfault on exit.
            self.compilation_tabs.pdf_viewer.doc.close()
            return True
        return False

    # noinspection PyDefaultArgument
    def update_recent_files_menu(self) -> None:
        recent_files = tuple(self.settings.recent_files)
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
        completed_process = install_desktop_shortcut()
        if completed_process.returncode == 0:
            # noinspection PyTypeChecker
            QMessageBox.information(
                self, "Shortcut installed", "This application was successfully added to start menu."
            )
        else:
            # noinspection PyTypeChecker
            QMessageBox.critical(self, "Unable to install shortcut", completed_process.stdout)

    def dbg_send_scintilla_command(self):
        if self.current_mcq_editor is not None:
            self.current_mcq_editor.dbg_send_scintilla_command()

    def get_temp_path(self, suffix: Literal["tex", "pdf"], doc_path: Path = None) -> Path | None:
        """Get the path of a temporary file corresponding to the current document."""
        if doc_path is None:
            doc = self.settings.current_doc
            if doc is None:
                return None
            doc_path = doc.path
            if doc_path is None:
                doc_path = Path(f"new-doc-{doc.doc_id}")
        return self.tmp_dir / f"{'' if doc_path is None else doc_path.stem}-{path_hash(doc_path)}.{suffix}"
