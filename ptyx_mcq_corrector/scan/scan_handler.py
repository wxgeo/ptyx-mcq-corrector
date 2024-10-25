"""
This part is responsible for the handling the scan process, so this is the core of the application.

Architecture:
- The ScannerManager exists in the main thread (the thread of the UI).
  When a scan is run, the ScannerManager will create a new QThread,
  and a new ScanWorker instance in this thread.
- The ScanWorker will supervise all the work, waiting from information from the scan process,
  and giving back this information to the ScannerManager.
  Since the ScanWorker is in another thread, it should not have any reference
  to the main window, any interface widget nor the ScannerManager.
  It will communicate with the ScannerManager using a slots and signals mechanism.
- The ScanWorker will create a new process for the scan, since this enables the user
  to kill the task if needed.
  Communication with this process will be done through a pipe.
- The process will send `EndConnection` to end the communication (if not, the worker will hang
  forever waiting for the next message).
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from ptyx_mcq_corrector.internal_state import Action
from ptyx_mcq_corrector.scan.scan_worker import ProcessInfo, ScanWorker

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow
from ptyx_mcq_corrector.scan.conflict_handlers import (
    McqAnswersRequest,
    McqNameRequest,
    McqIntegrityRequest,
    McqRequest,
)


class ScannerManager(QObject):
    """Scanner manager, which communicates with the ScanWorker in the other thread."""

    # The GUI will connect to those signals to update the interface.
    scan_started = pyqtSignal(name="scan_started")
    scan_ended = pyqtSignal(name="scan_ended")

    def __init__(self, main_window: "McqCorrectorMainWindow"):
        super().__init__(None)
        self.main_window = main_window
        self.current_process_info: ProcessInfo | None = None
        self.current_thread: QThread | None = None
        self.worker: ScanWorker | None = None
        self.scan_started.connect(self.main_window.file_events_handler.on_scan_started)
        self.scan_ended.connect(self.main_window.file_events_handler.on_scan_ended)

    @property
    def compilation_is_running(self) -> bool:
        return self.current_thread is not None

    def launch_scan(self):
        """Launch a new thread to scan selected documents.

        In this new thread, a ScanWorker instance will handle the scan
        and launch a new process.
        """
        current_file = self.main_window.state.current_file
        if current_file is not None:
            self.current_thread = thread = QThread(self.main_window)
            self.worker = worker = ScanWorker(current_file)
            worker.moveToThread(self.current_thread)
            worker.process_started.connect(self.on_scan_started)
            worker.finished.connect(self.on_scan_ended)
            worker.finished.connect(worker.deleteLater)
            worker.request.connect(self.main_window.file_events_handler.on_request)
            # noinspection PyUnresolvedReferences
            thread.started.connect(worker.generate)
            thread.started.connect(lambda: print("Scan thread started..."))
            thread.finished.connect(lambda: print("Scan thread ended."))
            thread.finished.connect(thread.deleteLater)
            thread.start()
            assert self.current_thread is not None

    def on_scan_started(self, process: ProcessInfo):
        """Actions executing once the scan process starts."""
        print("ScannerManager.on_scan_started()")
        assert self.current_process_info is None
        self.current_process_info = process
        self.scan_started.emit()

    def on_scan_ended(self):
        """Actions executing once the scan process ends."""
        print("ScannerManager.on_scan_ended()")
        self.worker = None
        self.current_thread.quit()
        self.current_thread.wait()
        self.current_thread = None
        self.current_process_info = None
        self.scan_ended.emit()

    def abort_scan(self):
        """Enable the user to abort the scan process."""
        if self.current_process_info is not None:
            process = self.current_process_info.process
            id_ = process.pid
            process.kill()
            pipe_other_side = self.current_process_info.pipe_other_side
            assert pipe_other_side is not None
            process.join()
            pipe_other_side.send(None)
            print(f"Process {id_} interrupted.")
            self.on_scan_ended()
