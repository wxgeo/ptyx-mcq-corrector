from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QTreeView, QWidget, QAbstractItemView


class IssuesViewer(QTreeView):
    def __init__(self, parent: QWidget):
        super().__init__(parent)

    def display_model(self, model: QStandardItemModel) -> None:
        self.expandAll()
        self.show()

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
