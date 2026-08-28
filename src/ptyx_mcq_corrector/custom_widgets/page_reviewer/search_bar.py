import fnmatch
import re
from typing import cast

from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QWidget

from ptyx_mcq_corrector.custom_widgets.items_list.items_model import ItemsModel
from ptyx_mcq_corrector.custom_widgets.items_list.types import ITEM_INFO, ItemInfo
from ptyx_mcq_corrector.custom_widgets.generic.search_widget import SearchWidget


class HideFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        assert model is not None
        index = model.index(source_row, 0, source_parent)
        item_info: ItemInfo = index.data(ITEM_INFO)
        # print(
        #     "accept row: ",
        #     "<None>" if item_info is None else (item_info.text, item_info.match_filter),
        # )
        return item_info is not None and item_info.match_filter


class SearchItems(SearchWidget):
    def __init__(self, parent: QWidget | None, model_filter: HideFilterProxy):
        super().__init__(parent)
        self.filter = model_filter

        def update_search() -> None:
            self.update_filtered_items(self.text())

        self.line_edit.textChanged.connect(update_search)
        self.case_checkbox.checkStateChanged.connect(update_search)
        self.regex_checkbox.checkStateChanged.connect(update_search)

    # def on_text_changed(self, text: str) -> None:
    #     self.update_filtered_items(text)

    def update_filtered_items(self, search: str | None = None) -> None:
        if search is None:
            search = self.text()
        model: ItemsModel = cast(ItemsModel, self.filter.sourceModel())
        _filter(model.invisibleRootItem(), search, case_sensitive=self.is_case_sensitive, regex=self.is_regex)
        self.filter.invalidateFilter()


def _search_test(search: str, text: str, case_sensitive: bool = False, regex: bool = False) -> bool:
    if not case_sensitive:
        search = search.casefold()
        text = text.casefold()
    if not regex and "*" in search or "?" in search or "[" in search:
        # Support Unix-like patterns, by converting them to regex.
        # Add a `*` at the end, to accept the string to match only a part of the text.
        search = fnmatch.translate(search + "*")
        regex = True
    if regex:
        return re.search(search, text) is not None
    else:
        return search in text


def _filter(
    item: QStandardItem | None, search: str, case_sensitive: bool = False, regex: bool = False
) -> bool:
    """
    Walk through the node and its descendants (DFS), and test if they match the search criteria.

    :param item: a QStandardItem or None
    :return: True if the node or any of its descendants matches the search criteria, False otherwise
    """
    if item is None:
        return False
    # Note that for the invisible root item, `item_info` will be `None`.
    item_info: ItemInfo | None = item.data(ITEM_INFO)
    n = item.rowCount()
    # if item_info is not None:
    #     print(f"{item_info.text!r}", n, item_info.selectable)
    if item_info is not None and n == 0 and not item_info.selectable:
        # print("Skipped:", f"{item_info.text!r}")
        found = False
    else:
        found = False if item_info is None else _search_test(search, item_info.text, case_sensitive, regex)
        # If an item matches the search criteria, then all its descendants are automatically considered to mach it too.
        # So, the search criteria is changed to "", so that it always matches.
        # However, be careful not to display the siblings if a previous sibling matches: so, let's create a new boolean.
        found_in_children = found
        for row in range(n):
            # Use `|`, not `or`, to always call `_filter()` (no lazy evaluation)!
            found_in_children |= _filter(item.child(row), search if not found else "", case_sensitive, regex)
        found = found or found_in_children
    if item_info is not None:
        item_info.match_filter = found
        print(f"{item_info.text!r}", f"display={item_info.match_filter}")
    return found
