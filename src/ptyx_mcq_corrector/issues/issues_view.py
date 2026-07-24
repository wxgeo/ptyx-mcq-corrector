from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QTreeView, QAbstractItemView, QStyleOptionViewItem, QWidget
from PyQt6.QtCore import Qt, QModelIndex, QSize
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QApplication

from ptyx_mcq_corrector.enhanced_widget import EnhancedWidget
from ptyx_mcq_corrector.issues.issues_model import IssueState, STATE_ROLE, IssueInfo, IssuesTypes, IssuesModel

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class IssueColor:
    PENDING = QColor(200, 30, 30)
    FIXED = QColor(90, 140, 90)


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

        # Give the icon some room if one was set
        if not option.icon.isNull():
            option.decorationSize = QSize(16, 16)


class IssuesViewer(QTreeView, EnhancedWidget):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        print(type(self.window()))
        self._model: IssuesModel | None = None

    def setModel(self, model: IssuesModel) -> None:
        super().setModel(model)
        self._model = model

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        super().currentChanged(current, previous)
        model = self._model
        if model is not None:
            item = model.itemFromIndex(current)
            if item is not None:
                issue = item.data()
                if issue is not None:
                    self.sync_issue_reviewer(issue=issue)

        # self.issue_selected.emit(item.data())

    def moveCursor(self, cursor_action, modifiers):
        index = super().moveCursor(cursor_action, modifiers)

        # Keep skipping while landing on a non-selectable item
        while index.isValid() and not (index.flags() & Qt.ItemFlag.ItemIsSelectable):
            if cursor_action == QAbstractItemView.CursorAction.MoveDown:
                next_index = self.indexBelow(index)
            elif cursor_action == QAbstractItemView.CursorAction.MoveUp:
                next_index = self.indexAbove(index)
            else:
                break  # don't try to handle Left/Right/Home/End here
            if not next_index.isValid():
                break  # reached top/bottom of tree, stop to avoid infinite loop
            index = next_index
        return index

    def display_issues(self):
        model = self._model
        if model is not None:
            model.update()
            self.setItemDelegate(IssueStateDelegate(self))
            self.expandAll()
            self.show()

    def sync_issue_reviewer(self, issue: IssueInfo) -> None:
        print("Selected:", issue)
        doc = self._model.state.parser.scan_data.used_docs_index[issue.doc]
        if issue.type == IssuesTypes.AMBIGUOUS_ANSWERS:
            print("Cas 1")
            page = doc.pages_index[issue.page]
            self.main_window.checkboxes.page = page
            self.main_window.main_area.setCurrentIndex(1)
