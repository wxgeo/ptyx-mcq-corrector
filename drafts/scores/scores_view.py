from PyQt6.QtWidgets import QTableView


class ScoresView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
