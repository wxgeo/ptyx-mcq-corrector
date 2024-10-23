import contextlib
import multiprocessing
import pickle
from dataclasses import dataclass
from multiprocessing import Process
from multiprocessing.connection import Connection
from pathlib import Path
from traceback import print_exception
from typing import TypedDict, NotRequired

from PyQt6.QtCore import QObject, pyqtSignal
from ptyx.shell import print_success, red, yellow
from ptyx_mcq.cli import scan
from ptyx_mcq.scan.data_gestion.conflict_handling.config import Config
from ptyx_mcq.tools.misc import CaptureLog

from ptyx_mcq_corrector.scan.conflict_handlers import (
    McqRequest,
    END_CONNECTION_REQUEST,
    CustomNamesReviewer,
    CustomAnswersReviewer,
    CustomIntegrityIssuesFixer,
    CustomDocHeaderDisplayer,
)


@dataclass
class ProcessInfo:
    process: Process
    pipe_this_side: Connection
    pipe_other_side: Connection


class ScanWorkerInfo(TypedDict):
    path: Path
    error: NotRequired[BaseException]
    info: NotRequired[str]
    log: str


class ScanWorker(QObject):
    """A worker, doing the work in its own thread.

    It communicates with main thread through a `ScannerManager` instance."""

    finished = pyqtSignal(dict, name="finished")
    process_started = pyqtSignal(ProcessInfo, name="process_started")
    request = pyqtSignal(McqRequest, name="request")

    def __init__(self, path: Path):
        super().__init__(None)
        self.path = path
        assert self.path is not None

    def generate(self) -> None:
        print("ScanWorker.generate()")
        return_data: ScanWorkerInfo = {"path": self.path, "log": ""}
        # log: CaptureLog | str = "Error, log couldn't be captured!"
        with CaptureLog() as log:
            try:
                return_data = self._generate()
            finally:
                return_data["log"] = log.getvalue()
                print("End of task: emit 'finished' event.")
                self.finished.emit(return_data)

    def _generate(self) -> ScanWorkerInfo:
        """Generate a LaTeX file.

        If `doc_path` is None, the LaTeX file corresponds to the current edited document.
        Else, `doc_path` must point to a .ptyx or .ex file.
        """
        # main_window = self.main_window
        # doc = main_window.settings.current_doc
        # editor = main_window.current_mcq_editor
        # latex_path = self._latex_file_path(doc_path=doc_path)
        # if doc is None or editor is None or latex_path is None:
        #     return
        # code = editor.text() if doc_path is None else doc_path.read_text(encoding="utf8")

        # Change current directory to the parent directory of the ptyx file.
        # This allows for relative paths in include directives when compiling.
        with contextlib.chdir(self.path.parent):
            # https://docs.python.org/3/library/multiprocessing.html#multiprocessing-start-methods
            ctx = multiprocessing.get_context("spawn")
            this_side: Connection
            other_side: Connection
            this_side, other_side = ctx.Pipe(duplex=True)
            process: Process = ctx.Process(  # type: ignore
                target=scan_path,
                args=(
                    self.path,
                    other_side,
                ),
            )
            # Share process with main thread, to enable user to kill it if needed.
            # This may prove useful if there is an infinite loop in user code
            # for example.
            self.process_started.emit(ProcessInfo(process, this_side, other_side))
            process.start()
            print(f"Waiting for process {process.pid}")

            return_data = self._main_loop(this_side, other_side)
            print(f"End of process {process.pid}")
        print("Process data successfully recovered.")

        return return_data

    def _main_loop(self, this_side: Connection, other_side: Connection) -> ScanWorkerInfo:
        return_data: ScanWorkerInfo = {"path": self.path, "log": "No log."}
        while (content := this_side.recv()) != END_CONNECTION_REQUEST:
            if isinstance(content, McqRequest):
                self.request.emit(content)
            elif isinstance(content, BaseException):
                # TODO: store all errors, not only last one.
                return_data["error"] = content
            else:
                raise ValueError(f"Unrecognized data: {content}")
        return return_data


def scan_path(path: Path, connection: Connection) -> None:
    """Scan documents from another process, using a Connection to communicate."""

    # Customize conflicts' handling process.
    Config.NamesReviewer = CustomNamesReviewer
    Config.AnswersReviewer = CustomAnswersReviewer
    Config.IntegrityIssuesFixer = CustomIntegrityIssuesFixer
    Config.DocHeaderDisplayer = CustomDocHeaderDisplayer
    Config.extensions_data["connection"] = connection

    try:
        scan(path)
        print_success(f"Scan completed: '{path}'.")
    except BaseException as e:
        # An error occurred, we will share it with the main process if we can.
        # For that, we have to test that the error is serializable, before sharing it through the pipe.
        # (To communicate between processes, objects are serialized and deserialized
        # using pickle, so only serializable objects can be shared).
        pickle_incompatibility = False
        try:
            if type(pickle.loads(pickle.dumps(e))) != type(e):
                pickle_incompatibility = True
        except BaseException:
            pickle_incompatibility = True
            raise
        finally:
            if pickle_incompatibility:
                print(red(f"ERROR: Exception {type(e)} is not compatible with pickle!"))
                print(yellow("Please open a bug report about it!"))
                # Do not try to serialize this incompatible exception,
                # this will fail, and may even generate segfaults!
                # Let's use a vanilla `RuntimeError` instead.
                # (Yet, we should make this exception compatible with pickle asap...)
                connection.send(RuntimeError(str(e)))
            else:
                connection.send(e)
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        print(e, type(e), repr(e))
        print_exception(e)
        print("xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    # End communication.
    connection.send(END_CONNECTION_REQUEST)
