from dataclasses import dataclass
from enum import Enum
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Literal

from ptyx.shell import print_error
from ptyx_mcq.scan.data_gestion.conflict_handling.config import Config
from ptyx_mcq.scan.data_gestion.conflict_handling.data_check.base import (
    AbstractNamesReviewer,
    AbstractAnswersReviewer,
    Action,
    AbstractDocHeaderDisplayer,
    DefaultAllDataIssuesFixer,
    DataCheckResult,
)
from ptyx_mcq.scan.data_gestion.conflict_handling.integrity_check.base import AbstractIntegrityIssuesFixer
from ptyx_mcq.scan.data_gestion.data_handler import DataHandler
from ptyx_mcq.scan.data_gestion.document_data import Page, PicData
from ptyx_mcq.tools.config_parser import DocumentId, StudentName
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

    pic_data: PicData


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

    def __init__(self, data_storage: DataHandler, doc_id: DocumentId):
        pass

    def display(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class CustomIntegrityIssuesFixer(AbstractIntegrityIssuesFixer):
    """Custom implementation of AbstractIntegrityIssuesFixer."""

    def select_version(
        self, scanned_doc_id: DocumentId, temp_doc_id: DocumentId, page: Page
    ) -> Literal[1, 2]:
        connection: Connection = Config.extensions_data["connection"]
        connection.send(
            McqIntegrityRequest(
                pic_path1=self.data_storage.absolute_pic_path_for_page(scanned_doc_id, page),
                pic_path2=self.data_storage.absolute_pic_path_for_page(temp_doc_id, page),
            )
        )
        match (answer := connection.recv()):
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
                pic_path=self.data_storage.absolute_pic_path_for_page(doc_id=doc_id, page=Page(1)),
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

    def edit_answers(self, doc_id: DocumentId, page: Page) -> tuple[Action, bool]:
        connection: Connection = Config.extensions_data["connection"]
        connection.send(McqAnswersRequest(pic_data=self.data[doc_id].pages[page]))
        answer = connection.recv()
        match answer:
            case Action(), bool():
                return answer
            case _:
                print_error(f"I can't handle the following answer: {answer!r}")
                raise NotImplementedError
