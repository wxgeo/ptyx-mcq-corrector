from PyQt6.QtGui import QStandardItemModel

from ptyx_mcq_corrector.internal_state import AppState


class ScoresModel(QStandardItemModel):
    def __init__(self, state: "AppState"):
        super().__init__()
