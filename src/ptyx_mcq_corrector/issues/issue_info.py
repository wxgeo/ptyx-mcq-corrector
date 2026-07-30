from dataclasses import dataclass
from enum import StrEnum

from PyQt6.QtCore import QModelIndex
from ptyx_mcq.scan.data.scan_data import ScanData
from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum

import ptyx_mcq_corrector.internal_state as internal_state


class IssueType(StrEnum):
    NAMES = "Names issues"
    AMBIGUOUS_ANSWERS = "Ambiguous answers"
    MISSING_PAGES = "Missing pages"
    DUPLICATES = "Duplicates"


@dataclass
class IssueInfo:
    index: QModelIndex
    type: IssueType
    doc_id: DocumentId
    page_num: PageNum | None

    def validate_state(self, scan_data: ScanData) -> bool:
        """Save the current state on the drive."""
        doc = scan_data.used_docs_index[self.doc_id]
        if self.type == IssueType.AMBIGUOUS_ANSWERS:
            # Save the checkboxes' states changes on the drive.
            assert (page_num := self.page_num) is not None
            page = doc.pages_index[page_num]
            page.pic.save_checkboxes_state(is_fix=True)
            return True
        elif self.type == IssueType.NAMES:
            # Test if the issue is really fixed:
            #  - the name must be unique
            #  - the name must be valid
            return internal_state.STATE.has_valid_student_name(self.doc_id)  # True if valid, False if not
        else:
            raise NotImplementedError
        # No need to validate name change, since it is automatically saved.
