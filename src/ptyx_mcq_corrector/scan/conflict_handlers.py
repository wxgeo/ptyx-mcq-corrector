from dataclasses import dataclass
from enum import Enum
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Literal

from ptyx.pretty_print import print_error
from ptyx_mcq.scan.data import ScanData, Picture
from ptyx_mcq.scan.data.conflict_gestion.config import Config
from ptyx_mcq.scan.data.conflict_gestion.data_check.fix import (
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
    Action,
    AbstractDocHeaderDisplayer,
    DefaultAllDataIssuesFixer,
    DataCheckResult,
)
from ptyx_mcq.scan.data.conflict_gestion.integrity_check.fix import AbstractIntegrityIssuesFixer
from ptyx_mcq.tools.config_parser import DocumentId, StudentName, PageNum
from ptyx_mcq.tools.misc import copy_docstring


# Send this custom object to indicate that the connection must be closed.
# (This is more explicit than None.)
class EndConnectionRequest:
    def __str__(self):
        return "<END_CONNECTION_REQUEST>"

    def __eq__(self, other):
        return isinstance(other, EndConnectionRequest)


END_CONNECTION_REQUEST = EndConnectionRequest()


class McqRequest:
    """Base class for all requests."""


@dataclass
class McqIntegrityRequest(McqRequest):
    """McqRequest to be sent to main process, asking for which document version to keep."""

    pic_path1: Path
    pic_path2: Path


@dataclass
class McqNameRequest(McqRequest):
    """McqRequest to be sent to main process, asking for the student name."""

    pic_path: Path
    suggestion: str


@dataclass
class McqAnswersRequest(McqRequest):
    """McqRequest to be sent to main process, asking for answers review."""

    picture: Picture


class IntegrityAnswer(Enum):
    KEEP_FIRST = 1
    KEEP_SECOND = 2
    NEXT = 3
    PREVIOUS = 4


class CustomAllDataIssuesFixer(DefaultAllDataIssuesFixer):
    """Custom AllDataIssuesFixer.

    Add the closing of the connection at the end of the run.
    """

    def run(self, check_result: DataCheckResult) -> None:
        super().run(check_result)
        connection: Connection = Config.extensions_data["connection"]
        connection.send(END_CONNECTION_REQUEST)


class CustomDocHeaderDisplayer(AbstractDocHeaderDisplayer):
    """A (void) implementation of AbstractDocHeaderDisplayer.

    It does nothing, since document display is already handled by the GUI.
    """

    def __init__(self, scan_data: ScanData, doc_id: DocumentId):
        pass

    def display(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class CustomIntegrityIssuesFixer(AbstractIntegrityIssuesFixer):
    """Custom implementation of AbstractIntegrityIssuesFixer."""

    def select_version(self, pic1: Picture, pic2: Picture) -> Literal[1, 2]:
        connection: Connection = Config.extensions_data["connection"]
        connection.send(McqIntegrityRequest(pic_path1=pic1.path, pic_path2=pic2.path))
        match answer := connection.recv():
            case IntegrityAnswer.KEEP_FIRST:
                return 1
            case IntegrityAnswer.KEEP_SECOND:
                return 2
            case _:
                print_error(f"I can't handle the following answer: {answer!r}")
                raise NotImplementedError


class CustomNamesReviewer(AbstractNamesReviewer):
    """Custom implementation of AbstractNamesReviewer."""

    @copy_docstring(AbstractNamesReviewer._does_user_confirm)
    def _does_user_confirm(self) -> bool:
        # The risk of error seems lower in the GUI.
        return True

    @copy_docstring(AbstractNamesReviewer._ask_user_for_name)
    def _ask_user_for_name(self, suggestion: str, doc_id: DocumentId) -> str:
        connection: Connection = Config.extensions_data["connection"]
        connection.send(
            McqNameRequest(
                pic_path=self.scan_data.all_docs_index[doc_id].pages_index[PageNum(1)].pic.path,
                suggestion=suggestion,
            )
        )
        answer = connection.recv()
        if not isinstance(answer, str):
            print_error(f"I can't handle the following answer: {answer!r}")
            raise NotImplementedError
        return StudentName(answer)


class CustomAnswersReviewer(AbstractAnswersReviewer):
    """Custom implementation of AbstractNamesReviewer."""

    def _edit_answers(self, doc_id: DocumentId, page_num: PageNum) -> Action:
        connection: Connection = Config.extensions_data["connection"]
        connection.send(
            McqAnswersRequest(picture=self.scan_data.all_docs_index[doc_id].pages_index[page_num].pic)
        )
        answer = connection.recv()
        match answer:
            case Action(), bool():
                return answer[0]
            case _:
                print_error(f"I can't handle the following answer: {answer!r}")
                raise NotImplementedError
