"""
This part is responsible for the handling the scan process, so this is the core of the application.

Architecture:
- The ScanManager exists in the main thread (the thread of the UI).
  It owns another thread, the "scan thread", in which all the scan related processes will take place.
  In this scan thread, a worker (of class `ScanWorker`) will handle the work. It will communicate
  with the main thread through Qt signals and slots mechanism.
- The ScanWorker will supervise all the work, waiting from information from the scan process,
  and giving back this information to the ScanManager.
  Since the ScanWorker is in another thread, it should not have any reference
  to the main window, any interface widget nor the ScanManager.
  It will only communicate with the ScanManager with this mechanism of slots and signals.
"""

from functools import wraps
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, ParamSpec, TypeVar, Concatenate, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from ptyx_mcq.scan import MCQPictureParser
from ptyx_mcq.scan.data import PageData, AnalyzeResult


if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

P = ParamSpec("P")
R = TypeVar("R")


def action(f: Callable[Concatenate["ScanManager", P], R]) -> Callable[Concatenate["ScanManager", P], R]:
    @wraps(f)
    def wrapper(self: "ScanManager", *args: P.args, **kw: P.kwargs):
        try:
            if self._is_busy:
                raise RuntimeError("ScanManager already busy.")
            self._is_busy = True
            f(self, *args, **kw)
        finally:
            self._is_busy = False

    return wrapper


class ScanManager(QObject):
    """The scan manager, which runs in a dedicated thread."""

    # The GUI will connect to those signals to update the interface.
    scan_started = pyqtSignal(name="scan_started")
    scan_ended = pyqtSignal(name="scan_ended")
    scan_aborted = pyqtSignal(name="scan_aborted")
    scan_progress = pyqtSignal(str, name="scan_progress")

    def __init__(self, main_window: "McqCorrectorMainWindow"):
        super().__init__(None)
        self.main_window = main_window
        self.scan_started.connect(self.main_window.file_events_handler.on_scan_started)
        self.scan_ended.connect(self.main_window.file_events_handler.on_scan_ended)
        self.scan_aborted.connect(self.main_window.file_events_handler.on_scan_aborted)
        self._is_busy = False

    @property
    def path(self) -> Path | None:
        return self.main_window.state.current_file

    @property
    def parser(self) -> MCQPictureParser | None:
        return self.main_window.state.parser

    @property
    def abort_event(self) -> Event:
        return self.main_window.file_events_handler.abort_event

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    def progression(self, info):
        msg = "Scan in progress..."
        if isinstance(info, PageData):
            data = info.identification_data
            msg = f"Retrieving page {data.page_num} of document #{data.doc_id}."
        elif isinstance(info, AnalyzeResult):
            students = [student for student in info.students if student is not None]
            if students:
                names = ", ".join(f"{student.name} ({student.id})" for student in students)
            else:
                names = "an unkwown student"
            msg = f"Analyzing the answers of {names}..."
        self.scan_progress.emit(msg)

    def scan(self):
        self._scan()

    @action
    def _scan(self: "ScanManager"):
        """Launch the scan process.

        This is the main entry point of the scan process.
        """
        if (parser := self.parser) is not None:
            self.scan_started.emit()
            parser.scan_data.run(progression=self.progression, abort_event=self.abort_event)
            if self.abort_event.is_set():
                self.scan_aborted.emit()
            else:
                self.scan_ended.emit()
