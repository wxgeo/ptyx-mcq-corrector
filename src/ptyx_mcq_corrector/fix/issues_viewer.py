from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QTreeView, QWidget


class IssuesViewer(QTreeView):
    def __init__(self, parent: QWidget):
        super().__init__(parent)

    def display_model(self, model: QStandardItemModel) -> None:
        self.setModel(model)
        self.expandAll()
        self.show()
