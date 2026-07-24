
from ptyx_mcq_corrector.fix.issues_model import IssuesModel
from ptyx_mcq_corrector.fix.issues_viewer import IssuesViewer
from ptyx_mcq_corrector.internal_state import State


class IssuesController:
    def __init__(self, state: State, view: IssuesViewer, model: IssuesModel):
        self.state = state
        self.view = view
        self.model = model

    def display_issues(self):
        self.model.update()
        self.view.display_model(self.model.tree_model)
