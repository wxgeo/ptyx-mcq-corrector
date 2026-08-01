from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ptyx_mcq_corrector.internal_state import STATE
from ptyx_mcq_corrector.scores.scores_model import ScoresModel
from ptyx_mcq_corrector.scores.scores_view import ScoresView


class ScoresDisplayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.scores_view = ScoresView(parent=self)
        self.scores_model = ScoresModel(state=STATE)
        self.scores_view.setModel(self.scores_model)
        layout.addWidget(self.scores_view)
