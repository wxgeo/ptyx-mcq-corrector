#!/usr/bin/python3
import signal
import sys
from argparse import ArgumentParser
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import Type

import argcomplete
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox
from argcomplete import FilesCompleter
from ptyx_mcq.parameters import CONFIG_FILE_EXTENSION

from ptyx_mcq_corrector.main_window import ICON_PATH, McqCorrectorMainWindow

from ptyx_mcq_corrector.signal_wake_up import SignalWakeupHandler


def my_excepthook(
    type_: Type[BaseException],
    value: BaseException,
    traceback: TracebackType | None,
    window: QMainWindow = None,
) -> None:
    # TODO: Log the exception here?
    # noinspection PyTypeChecker
    QMessageBox.critical(window, "Something went wrong!", f"{type(value).__name__}: {value}")
    # Call the default handler.
    sys.__excepthook__(type_, value, traceback)


def main(args: list | None = None) -> None:
    parser = ArgumentParser(description="Editor for pTyX and MCQ files.")
    parser.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        type=Path,
        help=f"One pTyX MCQ configuration file to open (with '{CONFIG_FILE_EXTENSION}' extension).",
    ).completer = FilesCompleter(  # type: ignore
        (CONFIG_FILE_EXTENSION,)
    )
    argcomplete.autocomplete(parser, always_complete_options=False)
    parsed_args = parser.parse_args(args)
    try:
        app = QApplication(sys.argv)
        app.setWindowIcon(QIcon(str(ICON_PATH)))
        # Used to handle Ctrl+C
        # https://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co
        SignalWakeupHandler(app)
        main_window = McqCorrectorMainWindow(parsed_args)
        # Don't close pyQt application on failure.
        sys.excepthook = partial(my_excepthook, window=main_window)
        # Used to handle Ctrl+C
        signal.signal(signal.SIGINT, lambda sig, _: app.quit())
        main_window.move(
            main_window.screen().geometry().center()  # type: ignore
            - QRect(QPoint(), main_window.frameGeometry().size()).center()
        )
        main_window.show()
        return_code = app.exec()
    except BaseException as e:
        raise e
    print("Bye!")
    sys.exit(return_code)


# TODO: support for arguments (file to open)
if __name__ == "__main__":
    main()
