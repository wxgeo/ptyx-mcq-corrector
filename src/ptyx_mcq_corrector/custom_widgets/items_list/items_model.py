from enum import Enum
from typing import Generator

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from ptyx_mcq.scan.data.documents import Document, Page
from ptyx_mcq.tools.parse_config.subtypes import DocumentId, PageNum
from ptyx_mcq_corrector.app_state import AppState
from ptyx_mcq_corrector.custom_widgets.items_list.types import (
    CategoryItemData,
    ITEM_INFO,
    ItemInfo,
    ItemType,
    CategoryTitle,
    DocTitle,
    PageTitle,
)


FoundIssues = dict[DocumentId, list[PageNum]] | list[DocumentId]

ISSUE_ROLE = Qt.ItemDataRole.UserRole + 1
STATE_ROLE = Qt.ItemDataRole.UserRole + 2


class IssueState(Enum):
    PENDING = "pending"
    FIXED = "fixed"


def _items_walker(model: QStandardItemModel):
    root = model.invisibleRootItem()
    stack: list[QStandardItem | None] = [root]
    while stack:
        item = stack.pop()
        if item is not None:
            yield item
            stack.extend((item.child(row) for row in range(item.rowCount())))


class ItemsModel(QStandardItemModel):
    def __init__(self, state: "AppState"):
        super().__init__()
        self.state = state
        # self.current_doc: DocumentId | None = None
        # self.current_page: PageNum | None = None
        # self.title: str = ""

    def update_model(self, *categories: CategoryItemData) -> bool:
        """
        Update the state of the model.

        Return `True` if any items were found, `False` otherwise.
        """
        self.clear()
        for category in categories:
            self._add_category(category)
        return len(categories) > 0

    def _add_category(self, category_item_data: CategoryItemData) -> None:
        """
        Add the items of this category to the model.
        """
        root = self.invisibleRootItem()
        assert root is not None
        category = category_item_data.name
        category_item = self._new_category(category)
        for doc_item_data in category_item_data.docs:
            doc = doc_item_data.doc
            # The final items may be either the docs themselves, in which case the docs are selectable, or their pages.
            #
            doc_item = self._new_doc(
                category_item,
                doc_item_data.name,
                selectable=not category_item_data.display_pages,
                category=category,
                doc=doc,
            )
            if category_item_data.display_pages:
                for page_item_data in doc_item_data.pages:
                    self._new_page(
                        doc_item, page_item_data.name, category=category, doc=doc, page=page_item_data.page
                    )

    @staticmethod
    def _new_item(
        parent: QStandardItem,
        title: str,
        selectable: bool,
        item_type: ItemType,
        category: CategoryTitle,
        doc: Document | None = None,
        page: Page | None = None,
    ) -> QStandardItem:
        item = QStandardItem(title)
        if not selectable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        parent.appendRow(item)
        item.setData(
            ItemInfo(index=item.index(), type=item_type, category=category, doc=doc, page=page), ITEM_INFO
        )
        return item

    def _new_category(self, name: CategoryTitle) -> QStandardItem:
        root = self.invisibleRootItem()
        assert root is not None
        return self._new_item(root, name, selectable=False, item_type=ItemType.CATEGORY, category=name)

    def _new_doc(
        self,
        category_item: QStandardItem,
        name: DocTitle,
        selectable: bool,
        category: CategoryTitle,
        doc: Document,
    ):
        return self._new_item(
            category_item, name, selectable=selectable, item_type=ItemType.DOC, category=category, doc=doc
        )

    def _new_page(
        self,
        category_item: QStandardItem,
        name: PageTitle,
        category: CategoryTitle,
        doc: Document,
        page: Page,
    ):
        return self._new_item(
            category_item,
            name,
            selectable=True,
            item_type=ItemType.PAGE,
            category=category,
            doc=doc,
            page=page,
        )

    def _walk(self) -> Generator[QStandardItem, None, None]:
        return _items_walker(self)

    @property
    def selectable_items(self) -> list[ItemInfo]:
        selectable_items: list[ItemInfo] = []
        print(self.rowCount())
        for item in self._walk():
            item_info: ItemInfo | None = item.data(ITEM_INFO)
            if item_info is not None and item_info.selectable:
                selectable_items.append(item_info)
        return selectable_items
