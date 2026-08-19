from dataclasses import dataclass, field
from enum import Enum, auto, StrEnum
from typing import ClassVar, Any, TypeVar, NewType, NamedTuple, TypedDict, Literal, Self

from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QTreeView, QStyle
from ptyx_mcq.scan.data.documents import Document, Page


class ItemStatus(Enum):
    FAILURE = auto()
    FIXED = auto()
    DEFAULT = auto()


# @dataclass
# class ItemStyle:
#     bold: bool = False
#     italic: bool = False
#     color: QColor | None = None
#     icon: QStyle.StandardPixmap | None = None


# class Styles(dict[ItemStatus, ItemStyle]):
#     def get_style(self, status: ItemStatus) -> ItemStyle:
#         return self.get(status, self.get(ItemStatus.DEFAULT, ItemStyle()))
#
#     @classmethod
#     def new(cls) -> "Styles":
#         return Styles({ItemStatus.DEFAULT: ItemStyle()})


class ItemType(StrEnum):
    CATEGORY = "category"
    DOC = "doc"
    PAGE = "page"


CategoryTitle = NewType("CategoryTitle", str)
DocTitle = NewType("DocTitle", str)
PageTitle = NewType("PageTitle", str)


# @dataclass
# class ItemData:
#     data: Any = None
#     status: ItemStatus = ItemStatus.DEFAULT


# @dataclass
# class Category:
#     name: CategoryTitle = CategoryTitle("")
#     docs: dict[DocTitle, dict[PageTitle, ItemData] | ItemData] = field(default_factory=dict)


@dataclass
class PageItemData:
    name: PageTitle
    page: Page


@dataclass
class DocItemData:
    name: DocTitle
    doc: Document
    pages: list[PageItemData] = field(default_factory=list)


@dataclass
class CategoryItemData:
    name: CategoryTitle = CategoryTitle("")
    docs: list[DocItemData] = field(default_factory=list)
    # Indicate if the pages are meant to be displayed. If so, the pages items will be selectable, but not the doc ones.
    # Else, the doc items will be selectable.
    display_pages: bool = True


ITEM_INFO = Qt.ItemDataRole.UserRole + 1


@dataclass
class ItemInfo:
    index: QModelIndex
    type: ItemType
    category: CategoryTitle
    doc: Document | None = None
    page: Page | None = None
    status: ItemStatus = ItemStatus.DEFAULT

    @property
    def selectable(self) -> bool:
        return bool(self.index.flags() & Qt.ItemFlag.ItemIsSelectable)


# @dataclass
# class Template:
#     category: Styles = field(default_factory=Styles.new)
#     doc: Styles = field(default_factory=Styles.new)
#     page: Styles = field(default_factory=Styles.new)
#
#     def get_style(self, item_info: ItemInfo) -> ItemStyle:
#         return getattr(self, item_info.type).get_style(item_info.status)
