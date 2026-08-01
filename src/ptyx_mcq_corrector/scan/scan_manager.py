"""
This part is responsible for the handling the scan process.

Architecture:
  The ScanManager lives in specific thread, so that any action won't block the user interface.
  It communicates with the main thread using Qt signals.
"""

from functools import wraps
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, ParamSpec, TypeVar, Concatenate, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from ptyx_mcq.scan.scan_doc import MCQPictureParser
from ptyx_mcq.scan.data.scan_data import PageData, AnalyzeResult

from ptyx_mcq_corrector.app_state import STATE

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
        return STATE.current_file

    @property
    def parser(self) -> MCQPictureParser | None:
        return STATE.parser

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

    # Warning:
    # When connecting a signal to a plain Python callable, PyQt inspects the callable's signature to decide
    # how many of the signal's arguments to actually pass — it only forwards as many as the slot appears to accept.
    # However, the @action decorator fools this pyQt mechanism: the ._scan() signature is not correctly detected.
    # So, the following method should never be used directly a slot, always use a wrapper instead.
    @action
    def _scan(self: "ScanManager"):
        """Launch the scan process.

        This is the main entry point of the scan process.
        """
        self.abort_event.clear()  # just in case
        if (parser := self.parser) is not None:
            self.scan_started.emit()
            parser.scan_data.run(progression=self.progression, abort_event=self.abort_event)
            if self.abort_event.is_set():
                self.scan_aborted.emit()
            else:
                self.scan_ended.emit()
