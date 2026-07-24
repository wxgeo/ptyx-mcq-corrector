from ptyx_mcq_corrector.fix.issues_model import IssuesModel
from ptyx_mcq_corrector.fix.issues_viewer import IssuesViewer
from ptyx_mcq_corrector.internal_state import State


class IssuesController:
    def __init__(self, state: State, view: IssuesViewer):
        self.state = state
        self.view = view
        self.model = IssuesModel(state)

    def display_issues(self):
        self.model.update()
        self.view.setModel(self.model.tree_model)
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
