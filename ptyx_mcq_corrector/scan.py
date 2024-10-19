"""
This part is responsible for the handling the scan process, so this is the core of the application.

Architecture:
- The ScannerManager exists in the main thread (the thread of the UI).
  When a scan is run, the ScannerManager will create a new QThread,
  and a new Worker instance in this thread.
- The Worker will supervise all the work, waiting from information from the scan process,
  and giving back this information to the ScannerManager.
  Since the Worker is in another thread, it should not have any reference
  to the main window, any interface widget nor the ScannerManager.
  It will communicate with the ScannerManager using a slots and signals mechanism.
- The Worker will create a new process for the scan, since this enables the user
  to kill the task if needed.
  Communication with this process will be done through a pipe.
- The process will send `None` to end the communication (if not, the worker will hang
  forever waiting for the next message).
"""

from pathlib import Path

from PyQt6.QtCore import QThread, QObject

from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class Worker(QObject):
    """A worker, doing the work in its own thread.

    It communicates with main thread through a `ScannerManager` instance."""

    def __init__(self, path: Path):
        super().__init__(None)


class ScannerManager:
    """Scanner manager, which communicates with the Worker in the other thread."""

    def __init__(self, main_window: McqCorrectorMainWindow):
        self.main_window = main_window
        self.current_thread = QThread(self.main_window)
        current_file = self.main_window.state.current_file
        assert current_file is not None
        self.worker = Worker(current_file)
        self.worker.move_to_thread(self.current_thread)
