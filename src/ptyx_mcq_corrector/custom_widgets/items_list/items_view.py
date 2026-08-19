from typing import TYPE_CHECKING, Callable, ClassVar

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QTreeView, QAbstractItemView, QStyleOptionViewItem, QWidget
from PyQt6.QtCore import Qt, QModelIndex, QSize
from PyQt6.QtGui import QColor, QPalette, QFont, QKeyEvent
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QApplication


# from ptyx_mcq_corrector.enhanced_widget import EnhancedWidget
from ptyx_mcq_corrector.issues_widget.issues_model import (
    IssueState,
    STATE_ROLE,
    IssuesModel,
    ISSUE_ROLE,
)


if TYPE_CHECKING:
    from ptyx_mcq_corrector.views.data_issues.page_reviewer import DataView


class ItemsViewer(QTreeView):
    def __init__(self, parent: QWidget | None, styliser: QStyledItemDelegate):
        super().__init__(parent)
        self._parent: "DataView" = parent  # type:ignore
        self.setHeaderHidden(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setItemDelegate(styliser)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        if (model := self.model()) is not None:
            assert isinstance(model, IssuesModel)
            item = model.itemFromIndex(current)
            if item is not None:
                issue = item.data(ISSUE_ROLE)
                if issue is not None:
                    self._parent.on_issue_selected(issue=issue)

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

    def update_issues(self) -> None:
        if (model := self.model()) is not None:
            assert isinstance(model, IssuesModel)
            model.update_model()
            self.expandAll()
            # self.show()

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
