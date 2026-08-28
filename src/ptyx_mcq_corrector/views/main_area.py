from enum import IntEnum
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QStackedWidget, QWidget, QMenu

from ptyx_mcq_corrector.app_state import STATE, State

from ptyx_mcq_corrector.custom_widgets.items_list.types import CategoryTitle
from ptyx_mcq_corrector.views.default.main_widget import DefaultView
from ptyx_mcq_corrector.views.integrity_issues.main_widget import IntegrityView
from ptyx_mcq_corrector.views.scores.main_widget import ScoresView
from ptyx_mcq_corrector.views.search_results.main_widget import SearchView
from ptyx_mcq_corrector.views.data_issues.main_widget import DataView
from ptyx_mcq_corrector.custom_widgets.page_reviewer.page_reviewer import Components

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class ViewMode(IntEnum):
    DEFAULT = 0
    INTEGRITY_ISSUES = 1
    DATA_ISSUES = 2
    SEARCH_RESULTS = 3
    SCORES = 4


DEFAULTS_VIEW_MODES: dict[State, ViewMode] = {
    State.NO_SCAN: ViewMode.DEFAULT,
    State.SCAN_IN_PROGRESS: ViewMode.DEFAULT,
    State.INTEGRITY_ISSUES: ViewMode.INTEGRITY_ISSUES,
    State.DATA_ISSUES: ViewMode.DATA_ISSUES,
    State.VALIDATED: ViewMode.SCORES,
}

ALLOWED_STATES: dict[ViewMode, list[State]] = {
    ViewMode.DEFAULT: [State.NO_SCAN, State.SCAN_IN_PROGRESS],
    ViewMode.INTEGRITY_ISSUES: [State.INTEGRITY_ISSUES],
    ViewMode.DATA_ISSUES: [State.DATA_ISSUES],
    ViewMode.SEARCH_RESULTS: [
        State.INTEGRITY_ISSUES,
        State.DATA_ISSUES,
        State.VALIDATED,
    ],
    ViewMode.SCORES: [State.VALIDATED],
}


class MainArea(QStackedWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._parent: McqCorrectorMainWindow = parent  # type: ignore

        self.default_view = DefaultView(self)
        self.addWidget(self.default_view)

        self.integrity_view = IntegrityView(self)
        self.addWidget(self.integrity_view)

        self.data_view = DataView(self)
        self.addWidget(self.data_view)

        self.search_view = SearchView(self)
        self.addWidget(self.search_view)

        self.scores_view = ScoresView(self)
        self.addWidget(self.scores_view)

        self._view_mode: ViewMode = ViewMode.DEFAULT

    @property
    def view_mode(self) -> ViewMode:
        return self._view_mode

    @view_mode.setter
    def view_mode(self, mode: ViewMode) -> None:
        assert STATE.state in ALLOWED_STATES[mode], STATE.state
        self._view_mode = mode

    @classmethod
    def _set_enabled(cls, menu: QMenu, enabled: bool) -> None:
        """Enable or disable a QMenu and all its actions, recursively."""
        menu.setEnabled(enabled)
        for action in menu.actions():
            action.setVisible(enabled)
            action.setEnabled(enabled)
            submenu = action.menu()
            if submenu is not None:
                # recurse into submenus
                cls._set_enabled(submenu, enabled)

    def _update_menu_bar(self) -> None:
        # Actions that make sense only when fixing issues.
        self._parent.menuReview.setEnabled(self.view_mode != ViewMode.DEFAULT)
        is_review = self.view_mode in (ViewMode.INTEGRITY_ISSUES, ViewMode.DATA_ISSUES)
        for action in [
            self._parent.actionPrevious,
            self._parent.actionNext,
            self._parent.actionValidate,
            self._parent.actionValidate_all_answers,
            self._parent.actionRefresh,
        ]:
            action.setVisible(is_review)
            action.setEnabled(is_review)

        # Actions that make sense only once there is no remaining issues.
        self._set_enabled(self._parent.menuScores, STATE.state >= State.VALIDATED)

        # Actions that make sense only once the scores have been computed.
        is_score_computed = STATE.scores is not None
        for action in [
            self._parent.action_Refresh_scores,
            self._parent.action_Open_in_Spreadsheet,
        ]:
            action.setVisible(is_score_computed)
            action.setEnabled(is_score_computed)

    def update_view(self) -> None:
        # TODO: handle scores' view
        self._update_menu_bar()
        print(self.view_mode)
        match self.view_mode:
            case ViewMode.DEFAULT:
                self._update_header()

            case ViewMode.DATA_ISSUES:
                item_info = self.data_view.issues_viewer.current_item
                print(item_info)
                if item_info is None:
                    self.data_view.page = None
                    self.data_view.components_to_display = Components.CBX_REVIEWER
                else:
                    match item_info.category:
                        case CategoryTitle.AMBIGUOUS_ANSWERS:
                            self.data_view.components_to_display = Components.CBX_REVIEWER
                            self.data_view.update_view()
                        case CategoryTitle.NAMES:
                            self.data_view.components_to_display = Components.NAME_EDITOR
                            self.data_view.update_view()
            case ViewMode.INTEGRITY_ISSUES:
                item_info = self.data_view.issues_viewer.current_item
                print(item_info)
                if item_info is None:
                    ...  # TODO
                else:
                    match item_info.category:
                        case CategoryTitle.DUPLICATES:
                            ...  # TODO
                        case CategoryTitle.MISSING_PAGES:
                            ...  # TODO
            case ViewMode.SEARCH_RESULTS:
                self.search_view.update_view()
            case ViewMode.SCORES:
                ...  # TODO
            # case ViewMode.CORRECTIONS:
            #     ...  # TODO

            case _:
                raise NotImplementedError
        self.setCurrentIndex(self.view_mode)

    def _update_header(self) -> None:
        label = self.default_view.header_label
        if STATE.current_file is None:
            label.setText("No document")

        elif STATE.state == State.SCAN_IN_PROGRESS:
            msg = f"Starting scan of '{STATE.current_file}'..."
            print(msg)
            label.setText(msg)

        else:
            label.setText(STATE.current_file_shortname)
            # Any non-null value is OK for `href`, but it can't be left empty, else Qt doesn't generate a link at all.
            label.setText(
                "<p style='text-align:center'>Document <i><b>"
                f"<a href='#'>{STATE.current_file_shortname}</a>"
                "</b></i> selected.</p>"
                "<p style='text-align:center;font-size:small'>Press <b>F5</b> to start scanning.</p>"
            )
            try:
                label.linkActivated.disconnect()
            except TypeError:
                pass  # no connection existed yet
            label.linkActivated.connect(lambda _: self._parent.file_events_handler.open_file())
            label.setOpenExternalLinks(False)
