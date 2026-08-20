from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QTreeView, QAbstractItemView, QStyleOptionViewItem, QWidget
from PyQt6.QtCore import Qt, QModelIndex, QSize
from PyQt6.QtGui import QColor, QPalette, QFont, QKeyEvent
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QApplication

from ptyx_mcq_corrector.custom_widgets.items_list.items_model import ItemsModel
from ptyx_mcq_corrector.custom_widgets.items_list.types import ITEM_INFO, ItemInfo, ItemStatus, ItemType


if TYPE_CHECKING:
    from ptyx_mcq_corrector.views.data_issues.page_reviewer import DataView


class StatusColor:
    FAILURE = QColor(200, 30, 30)
    FIXED = QColor(90, 140, 90)


class Styliser(QStyledItemDelegate):
    """
    Computes foreground color and icon from STATE_ROLE at paint time,
    instead of relying on data stored per-item via setForeground/setIcon.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        # Load icons once, reuse for every paint call
        style = QApplication.style()
        assert style is not None
        self._pending_icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        self._fixed_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        # self._fixed_icon = QIcon("icons/issue_fixed.png")

    def initStyleOption(self, option: QStyleOptionViewItem | None, index: QModelIndex) -> None:
        super().initStyleOption(option, index)

        item_info: ItemInfo = index.data(ITEM_INFO)
        assert option is not None
        assert item_info is not None
        if item_info.status == ItemStatus.FAILURE:
            option.palette.setColor(QPalette.ColorRole.Text, StatusColor.FAILURE)
            option.icon = self._pending_icon
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
        elif item_info.status == ItemStatus.FIXED:
            option.palette.setColor(QPalette.ColorRole.Text, StatusColor.FIXED)
            option.icon = self._fixed_icon
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration

        font = QFont(option.font)  # make a copy to not mutate used font!
        if item_info.type == ItemType.CATEGORY:
            font.setBold(True)
        elif item_info.type == ItemType.DOC:
            font.setItalic(True)
        option.font = font

        # Give the icon some room if one was set
        if not option.icon.isNull():
            option.decorationSize = QSize(16, 16)
        # print("Style applied!", item_info)


class ItemsViewer(QTreeView):
    item_selected = pyqtSignal(ItemInfo, name="item_selected")

    def __init__(self, parent: QWidget | None, styliser: QStyledItemDelegate | None = None):
        super().__init__(parent)
        self._parent: "DataView" = parent  # type:ignore
        self.setHeaderHidden(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.styliser: QStyledItemDelegate = Styliser(self) if styliser is None else styliser
        self.current_item: ItemInfo | None = None

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        if (model := self.model()) is not None:
            assert isinstance(model, ItemsModel)
            item = model.itemFromIndex(current)
            if item is None:
                self.current_item = None
            else:
                item_info = item.data(ITEM_INFO)
                self.current_item = item_info
                if item_info is not None:
                    self.item_selected.emit(item_info)

    def moveCursor(
        self, cursor_action: QAbstractItemView.CursorAction, modifiers: Qt.KeyboardModifier
    ) -> QModelIndex:
        if cursor_action == QAbstractItemView.CursorAction.MoveDown:
            return self._navigate(self.indexBelow)
        elif cursor_action == QAbstractItemView.CursorAction.MoveUp:
            return self._navigate(self.indexAbove)
        return super().moveCursor(cursor_action, modifiers)

    def _navigate(self, step_func: Callable[[QModelIndex], QModelIndex]) -> QModelIndex:
        original_index = index = self.currentIndex()
        while (index := step_func(index)).isValid():
            if index.flags() & Qt.ItemFlag.ItemIsSelectable:
                return index
            # last_index = index
        return original_index

    def move_to_next_index(self) -> None:
        self.setCurrentIndex(self._navigate(self.indexBelow))

    def move_to_previous_index(self) -> None:
        self.setCurrentIndex(self._navigate(self.indexAbove))

        # def update_issues(self) -> None:
        #     if (model := self.model()) is not None:
        #         assert isinstance(model, IssuesModel)
        #         model.update_model()
        #         self.expandAll()
        #         # self.show()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        assert event is not None
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            # Give focus to the issue reviewer.
            self._parent.setFocus()
        elif event.key() == Qt.Key.Key_Right:
            self.move_to_next_index()
        elif event.key() == Qt.Key.Key_Left:
            self.move_to_previous_index()
        else:
            super().keyPressEvent(event)

    def update_view(self):
        self.setItemDelegate(self.styliser)
        self.expandAll()
