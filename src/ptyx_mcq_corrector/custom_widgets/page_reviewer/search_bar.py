from typing import cast

from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QWidget, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QSizePolicy,
)

from ptyx_mcq_corrector.custom_widgets.items_list.items_model import ItemsModel
from ptyx_mcq_corrector.custom_widgets.items_list.types import ITEM_INFO, ItemInfo


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


class SearchWidget(QWidget):
    """
    A compact search box:
      [ QLineEdit .................. ] [v]
        (hidden by default) case sensitive / regex checkboxes
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- line edit -------------------------------------------------
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Search…")

        # --- toggle button (arrow) -------------------------------------
        self.toggle_button = QToolButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setFixedWidth(18)
        self.toggle_button.setToolTip("Show search options")
        self.toggle_button.clicked.connect(self._on_toggle)

        # --- checkboxes (options row) -----------------------------------
        self.case_checkbox = QCheckBox("Case sensitive")
        self.regex_checkbox = QCheckBox("Regex")

        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(4, 0, 0, 0)
        options_layout.setSpacing(10)
        options_layout.addWidget(self.case_checkbox)
        options_layout.addWidget(self.regex_checkbox)
        options_layout.addStretch()

        # Wrap options in a frame so we can hide/show it as one unit,
        # and so it takes zero height when collapsed.
        self.options_frame = QFrame()
        self.options_frame.setLayout(options_layout)
        self.options_frame.setVisible(False)
        self.options_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # --- top row: line edit + toggle --------------------------------
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(2)
        top_row.addWidget(self.line_edit)
        top_row.addWidget(self.toggle_button)

        # --- main layout --------------------------------------------------
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        main_layout.addLayout(top_row)
        main_layout.addWidget(self.options_frame)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _on_toggle(self, checked: bool):
        self.options_frame.setVisible(checked)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.toggle_button.setToolTip("Hide search options" if checked else "Show search options")
        # Ask the top-level window to recompute its size so the widget
        # actually shrinks/grows instead of leaving empty space.
        window = self.window()
        if window is not None:
            window.adjustSize()

    # --- convenience accessors -----------------------------------------
    def text(self) -> str:
        return self.line_edit.text()

    def is_case_sensitive(self) -> bool:
        return self.case_checkbox.isChecked()

    def is_regex(self) -> bool:
        return self.regex_checkbox.isChecked()


class SearchItems(SearchWidget):
    def __init__(self, parent: QWidget | None, model_filter: HideFilterProxy):
        super().__init__(parent)
        self.filter = model_filter

        self.line_edit.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text: str) -> None:
        self.update_filtered_items(text)
        self.filter.invalidateFilter()

    def update_filtered_items(self, search: str | None = None) -> None:
        if search is None:
            search = self.text()
        model: ItemsModel = cast(ItemsModel, self.filter.sourceModel())
        _filter(model.invisibleRootItem(), search)
        self.filter.invalidateFilter()


def _filter(item: QStandardItem | None, search: str) -> bool:
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
        found = False if item_info is None else search in item_info.text
        # If an item matches the search criteria, then all its descendants are automatically considered to mach it too.
        # So, the search criteria is changed to "", so that it always matches.
        for row in range(n):
            found |= _filter(item.child(row), search if not found else "")
    if item_info is not None:
        item_info.match_filter = found
        # print(f"{item_info.text!r}", f"display={item_info.match_filter}")
    return found
