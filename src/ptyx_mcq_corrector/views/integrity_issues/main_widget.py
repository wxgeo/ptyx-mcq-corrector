from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum

from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.items_list.items_model import ItemsModel
from ptyx_mcq_corrector.custom_widgets.items_list.items_view import ItemsViewer
from ptyx_mcq_corrector.custom_widgets.items_list.types import (
    CategoryItemData,
    DocItemData,
    PageItemData,
    PageTitle,
    DocTitle,
    CategoryTitle,
)

_ERROR_COLOR = "#ad1827"


class IntegrityView(QWidget):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        main_layout = QHBoxLayout(self)
        self.issues_viewer = ItemsViewer(self)
        main_layout.addWidget(self.issues_viewer, 0)
        self.issues_model = ItemsModel(STATE)
        self.issues_viewer.setModel(self.issues_model)

        self.info = QLabel()
        main_layout.addWidget(self.info, alignment=Qt.AlignmentFlag.AlignTop)

    def update_info(self) -> None:
        html: list[str] = [f"<h1 style='color: {_ERROR_COLOR};'>Errors</h1>"]
        assert STATE.integrity_issues is not None
        assert STATE.integrity_issues is not None
        categories = {
            "Missing": (STATE.integrity_issues.missing_pages, "not found."),
            "Duplicates": (STATE.integrity_issues.duplicates, "found in different versions."),
        }

        for title, (issues, msg) in categories.items():
            if issues:
                html.append(f"<h2><strong style='color: {_ERROR_COLOR}'>⚠</strong> {title} pages</h2><ul>")
                for doc_id, pages in issues.items():
                    pages_description = ("page " if len(pages) == 1 else "pages ") + ", ".join(
                        map(str, pages)
                    )
                    html.append(f"<li><strong>Document {doc_id}:</strong> {pages_description} {msg}</li>")
                html.append("</ul>")
        html.append(
            "<p style='margin-top:20px'><strong>Please fix the scanned documents and retry.</strong></p>"
        )
        self.info.setText("\n".join(html))
        self.info.setStyleSheet(f"""
    QLabel {{border: 2px solid {_ERROR_COLOR};
        border-radius: 10px;
        padding: 10px;
        margin: 10px;
        padding-bottom: 20px;
    }}
""")

    @staticmethod
    def _issues_data(
        category_name: CategoryTitle, issues: dict[DocumentId, list[PageNum]]
    ) -> CategoryItemData:
        assert STATE.parser is not None
        docs_index = STATE.parser.scan_data.used_docs_index
        docs: list[DocItemData] = []
        for doc_id, page_nums in issues.items():
            doc = docs_index[doc_id]
            pages: list[PageItemData] = []
            for page_num in page_nums:
                # The page may be missing!
                page = doc.pages_index.get(page_num)
                pages.append(PageItemData(name=PageTitle(f"Page {page_num}"), page=page))
            docs.append(DocItemData(name=DocTitle(f"Document {doc_id}"), doc=doc, pages=pages))
        return CategoryItemData(name=category_name, docs=docs, display_pages=True)

    def update_issues(self) -> None:
        assert STATE.integrity_issues is not None
        self.issues_model.update_model(
            self._issues_data(CategoryTitle.DUPLICATES, STATE.integrity_issues.duplicates),
            self._issues_data(CategoryTitle.MISSING_PAGES, STATE.integrity_issues.missing_pages),
        )
        self.issues_viewer.update_view()
        self.update_info()
