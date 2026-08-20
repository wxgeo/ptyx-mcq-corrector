from enum import Flag
from typing import TYPE_CHECKING


from PyQt6.QtCore import QModelIndex
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy

from ptyx_mcq.scan.data.documents import Page


from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.items_list.items_model import ItemsModel
from ptyx_mcq_corrector.custom_widgets.items_list.items_view import ItemsViewer
from ptyx_mcq_corrector.custom_widgets.items_list.types import (
    ItemInfo,
    CategoryTitle,
    CategoryItemData,
    DocItemData,
    DocTitle,
    PageItemData,
    PageTitle,
    ITEM_INFO,
    ItemStatus,
)
from ptyx_mcq_corrector.enhanced_widget import EnhancedWidget
from ptyx_mcq_corrector.tools import update_ui
from ptyx_mcq_corrector.views.data_issues.cbx_reviewer import CheckboxesReviewer
from ptyx_mcq_corrector.views.data_issues.name_editor import NameEditor

if TYPE_CHECKING:
    pass


class Components(Flag):
    NONE = 0
    NAME_EDITOR = 1
    CBX_REVIEWER = 2
    BOTH = 3


class DataIssuesModel(ItemsModel):
    def validate(self, index: QModelIndex) -> bool:
        item_info: ItemInfo = index.data(ITEM_INFO)
        if item_info.selectable:
            item = self.itemFromIndex(index)
            assert item is not None
            # issue: IssueInfo = item.data(ISSUE_ROLE)
            match item_info.category:
                case CategoryTitle.NAMES:
                    result = self._validate_name(item_info)
                case CategoryTitle.AMBIGUOUS_ANSWERS:
                    result = self._validate_answers(item_info)
                case _:
                    raise NotImplementedError
            if result:
                # Mark the issue as fixed.
                item_info.status = ItemStatus.FIXED
                print("Issue marked as fixed.")
                return True
            else:
                print("Issue does not seem to be fixed yet.")
        return False

    def _validate_name(self, item_info: ItemInfo) -> bool:
        doc = item_info.doc
        assert doc is not None
        return STATE.has_valid_student_name(doc.doc_id)  # True if valid, False if not

    def _validate_answers(self, item_info: ItemInfo) -> bool:
        page = item_info.page
        assert page is not None
        page.pic.save_checkboxes_state(is_fix=True)
        return True


class DataView(EnhancedWidget):
    # main_window: "McqCorrectorMainWindow"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        main_layout = QHBoxLayout(self)
        self.issues_viewer = ItemsViewer(self)
        main_layout.addWidget(self.issues_viewer, 0)
        self.issues_model = DataIssuesModel(STATE)
        self.issues_viewer.setModel(self.issues_model)

        layout = QVBoxLayout()
        self.name_editor = NameEditor(self)
        self.name_editor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.name_editor)
        self.page_view = CheckboxesReviewer(self)
        self.page_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.page_view)

        main_layout.addLayout(layout, 1)

        self.components_to_display: Components = Components.NONE
        self.update_view()
        self.page_view.previous_page_requested.connect(self.issues_viewer.move_to_previous_index)
        self.page_view.next_page_requested.connect(self.issues_viewer.move_to_next_index)
        self.page_view.esc_requested.connect(self.issues_viewer.setFocus)

        self.issues_viewer.item_selected.connect(self.on_issue_selected)

    @staticmethod
    def _name_suggestions() -> list[str]:
        return sorted([student.to_text() for student in STATE.students])

    def update_view(self):
        self.name_editor.setVisible(Components.NAME_EDITOR in self.components_to_display)
        self.name_editor.update_suggestions()

        self.page_view.checkbox_review = Components.CBX_REVIEWER in self.components_to_display
        match self.components_to_display:
            case Components.BOTH:
                color = "magenta"
            case Components.NAME_EDITOR:
                color = "crimson"
            case Components.CBX_REVIEWER:
                color = "cornflowerblue"
            case _:
                color = "black"
        self.page_view.focus_rect_color = QColor(color)

    @property
    def _name_issues(self) -> CategoryItemData:
        docs: list[DocItemData] = []
        assert STATE.data_issues is not None
        assert STATE.parser is not None
        for doc_id in STATE.data_issues.names_to_review:
            doc = STATE.parser.scan_data.used_docs_index[doc_id]
            docs.append(DocItemData(name=DocTitle(f"Document {doc_id}"), doc=doc))
        return CategoryItemData(name=CategoryTitle.NAMES, docs=docs, display_pages=False)

    @property
    def _ambiguous_answers(self) -> CategoryItemData:
        assert STATE.parser is not None
        assert STATE.data_issues is not None
        docs_index = STATE.parser.scan_data.used_docs_index
        docs: list[DocItemData] = []
        for doc_id, page_nums in STATE.data_issues.ambiguous_answers_by_doc.items():
            doc = docs_index[doc_id]
            pages: list[PageItemData] = []
            for page_num in page_nums:
                page = doc.pages_index[page_num]
                pages.append(PageItemData(name=PageTitle(f"Page {page_num}"), page=page))
            docs.append(DocItemData(name=DocTitle(f"Document {doc_id}"), doc=doc, pages=pages))
        return CategoryItemData(name=CategoryTitle.AMBIGUOUS_ANSWERS, docs=docs, display_pages=True)

    def update_issues(self) -> None:
        self.issues_model.update_model(self._name_issues, self._ambiguous_answers)
        self.issues_viewer.expandAll()

    @property
    def page(self) -> Page:
        return self.page_view.page

    @page.setter
    def page(self, page: Page | None) -> None:
        self.page_view.page = page
        self.name_editor.set_current_student(None if page is None else page.pic.student)

    def validate_issue(self):
        print("Validating issue")
        if (item_info := self.issues_viewer.current_item) is not None:
            if self.issues_model.validate(item_info.index):
                self.issues_viewer.move_to_next_index()

    def validate_all_answers(self):
        print("validating all ambiguous answers issues")
        for item_info in self.issues_model.selectable_items:
            if item_info.type == CategoryTitle.AMBIGUOUS_ANSWERS:
                self.issues_model.validate(item_info.index)

    @update_ui
    def on_issue_selected(self, item_info: ItemInfo) -> bool:
        assert item_info is not None
        # STATE.current_issue = item_info.category  # To do at first!
        parser = STATE.parser
        assert parser is not None
        doc = item_info.doc
        assert doc is not None
        # Be careful to select the reviewer only *AFTER* the state have been changed.
        match item_info.category:
            case CategoryTitle.NAMES:
                self.page = doc.first_page
            case CategoryTitle.AMBIGUOUS_ANSWERS:
                self.page = item_info.page
                assert item_info.page is not None
        self.page_view.setFocus()
        return True
