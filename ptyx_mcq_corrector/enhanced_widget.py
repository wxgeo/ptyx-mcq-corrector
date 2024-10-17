from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow


class EnhancedWidget(QWidget):
    def _get_main_window(self) -> "McqCorrectorMainWindow":
        from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

        widget: QWidget = self
        while widget.parent() is not None:
            widget = widget.parent()  # type: ignore
        assert isinstance(widget, McqCorrectorMainWindow), widget
        return widget

    # TODO: use a cache ?
    @property
    def main_window(self):
        return self._get_main_window()
