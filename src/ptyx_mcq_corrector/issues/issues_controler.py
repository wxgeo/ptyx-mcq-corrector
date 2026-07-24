from typing import TYPE_CHECKING
from unittest import main

from PyQt6.QtCore import pyqtSignal, QObject

from ptyx_mcq_corrector.issues.issues_model import IssuesModel, IssueInfo
from ptyx_mcq_corrector.issues.issues_viewer import IssuesViewer, IssueStateDelegate
from ptyx_mcq_corrector.internal_state import State

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class IssuesController(QObject):
    issue_selected = pyqtSignal(IssueInfo, name="issue_selected")

    def __init__(self, parent: "McqCorrectorMainWindow"):
        super().__init__(parent)
        self.state = parent.state
        self.view = parent.issuesView
        self.model = IssuesModel(self.state)
        self.main_window = parent

    def display_issues(self):
        self.model.update()
        self.view.setModel(self.model.tree_model)
        self.view.setItemDelegate(IssueStateDelegate(self.view))
        selection_model = self.view.selectionModel()
        assert selection_model is not None
        try:
            selection_model.selectionChanged.disconnect(self.on_selection_changed)
        except TypeError:
            pass  # wasn't connected yet — nothing to disconnect
        selection_model.selectionChanged.connect(self.on_selection_changed)
        self.view.display_model(self.model.tree_model)

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            index = indexes[0]
            item = self.model.tree_model.itemFromIndex(index)
            assert item is not None
            print("Selected:", item.data())
            self.issue_selected.emit(item.data())
