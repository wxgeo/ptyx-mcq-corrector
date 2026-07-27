from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QTreeView, QAbstractItemView, QStyleOptionViewItem, QWidget
from PyQt6.QtCore import Qt, QModelIndex, QSize
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QApplication

from ptyx_mcq_corrector.enhanced_widget import EnhancedWidget
from ptyx_mcq_corrector.issues.issues_model import (
    IssueState,
    STATE_ROLE,
    IssuesModel,
    ISSUE_ROLE,
)

if TYPE_CHECKING:
    pass


class IssueColor:
    PENDING = QColor(200, 30, 30)
    FIXED = QColor(90, 140, 90)


def index_level(index: QModelIndex) -> int:
    level = 0
    parent = index.parent()
    while parent.isValid():
        level += 1
        parent = parent.parent()
    return level


class IssueStateDelegate(QStyledItemDelegate):
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

        state = index.data(STATE_ROLE)
        assert option is not None
        if state == IssueState.PENDING:
            option.palette.setColor(QPalette.ColorRole.Text, IssueColor.PENDING)
            option.icon = self._pending_icon
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration
        elif state == IssueState.FIXED:
            option.palette.setColor(QPalette.ColorRole.Text, IssueColor.FIXED)
            option.icon = self._fixed_icon
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasDecoration

        font = QFont(option.font)  # make a copy to not mutate used font!
        if index_level(index) == 0:
            font.setBold(True)
        if index_level(index) == 1:
            font.setItalic(True)
        option.font = font

        # Give the icon some room if one was set
        if not option.icon.isNull():
            option.decorationSize = QSize(16, 16)


class IssuesViewer(QTreeView, EnhancedWidget):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        if (model := self.model()) is not None:
            assert isinstance(model, IssuesModel)
            item = model.itemFromIndex(current)
            if item is not None:
                issue = item.data(ISSUE_ROLE)
                if issue is not None:
                    self.main_window.file_events_handler.on_issue_selected(issue=issue)

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

    def display_issues(self) -> None:
        if (model := self.model()) is not None:
            assert isinstance(model, IssuesModel)
            model.update()
            self.setItemDelegate(IssueStateDelegate(self))
            self.expandAll()
            self.show()

    def keyPressEvent(self, event):
        assert event is not None
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            # Give focus to the issue reviewer.
            if (current_reviewer := self.main_window.current_reviewer) is not None:
                current_reviewer.setFocus()
        elif event.key() == Qt.Key.Key_Right:
            self.move_to_next_index()
        elif event.key() == Qt.Key.Key_Left:
            self.move_to_previous_index()
        else:
            super().keyPressEvent(event)
