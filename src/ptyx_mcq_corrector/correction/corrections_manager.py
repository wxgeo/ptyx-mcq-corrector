from typing import TYPE_CHECKING

from ptyx_mcq.scan.data.amend import amend_doc, get_max_score_per_question
from ptyx_mcq.scan.data.documents import Document
from ptyx_mcq.tools.parse_config.subtypes import DocumentId
from ptyx_mcq_corrector.priority_doc_pool import DocumentGeneratorPool

if TYPE_CHECKING:
    from ptyx_mcq_corrector.app_state import AppState


def generate_correction_if_needed(payload: dict) -> None:
    """
    Generate the PDF file containing the correction of the document.

    If the document does already exist, do nothing.
    (Remove the document first and clear the DocumentGeneratorPool's cache if you want to regenerate it).
    """

    if not payload["doc"].correction_path.is_file():
        amend_doc(payload["doc"], payload["max_scores"])


class CorrectionsManager:
    def __init__(self, state: "AppState"):
        self._state = state
        self.docs_generator = DocumentGeneratorPool(generate_correction_if_needed)
        self.docs_generator.document_failed.connect(self.on_document_failed)
        self.docs_generator.document_ready.connect(self.on_document_ready)

    def pregenerate_all_docs(self) -> None:
        max_scores = get_max_score_per_question(self._state.parser.config)
        doc: Document
        for doc in self._state.parser.scan_data.sorted_by("student_name"):
            if not doc.correction_path.is_file():
                self.docs_generator.generate(doc.doc_id, {"doc": doc, "max_scores": max_scores})

    def generate_doc_now(self, doc: Document) -> None:
        max_scores = get_max_score_per_question(self._state.parser.config)
        self.docs_generator.generate(doc.doc_id, {"doc": doc, "max_scores": max_scores}, prioritize=True)

    def on_document_failed(self, doc_id: DocumentId, err: str):
        print(f"doc {doc_id} generation failed: '{err}'!")

    def on_document_ready(self, doc_id: DocumentId, answer: object):
        print(f"doc {doc_id} ready!")
