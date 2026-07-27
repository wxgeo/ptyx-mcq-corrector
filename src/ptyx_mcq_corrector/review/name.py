"""
MCQCheckboxWidget
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Draws rectangles around detected checkboxes, overlaid on the scan.
  3. Lets the user click a checkbox to toggle its checked / unchecked state,
     redrawing it (color + checkmark) live.
"""

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QLineEdit, QLabel, QHBoxLayout, QCompleter

from ptyx_mcq_corrector.review.generic_reviewer import PixReviewer

if TYPE_CHECKING:
    from ptyx_mcq_corrector.main_window import McqCorrectorMainWindow

# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


class NameEditor(QWidget):
    def __init__(self, parent: "McqCorrectorMainWindow"):
        super().__init__(parent)
        self.main_window: "McqCorrectorMainWindow" = parent
        self.name_editor = QLineEdit(self)
        self.name_editor.setStyleSheet("QLineEdit { margin-left: 15px; margin-right: 20px;}")
        label = QLabel("&Name/Id:")
        label.setStyleSheet("QLabel {color: red;}")
        label.setBuddy(self.name_editor)
        completer = QCompleter(self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.name_editor.setCompleter(completer)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        layout.addWidget(self.name_editor)

    def set_suggestions(self, names: list[str]):
        model = QStringListModel(names, self)
        assert (completer := self.name_editor.completer()) is not None
        completer.setModel(model)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.main_window.issuesView.setFocus()


class NameReviewer(PixReviewer):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    _name: str
    _id: str

    FOCUS_RECT_COLOR: QColor = QColor("magenta")

    def reset(self) -> None:
        super().reset()
        self._name = ...  # TODO
        self._id = ...  # TODO

    # ---- public API ----------------------------------------------------

    def _on_page_set(self) -> None:
        if (page := self.page) is not None:
            self._name = ...  # TODO

    def validate(self) -> None:
        """Save the checkboxes' states changes on the drive."""
        if (page := self.page) is not None:
            ...  # TODO: save name and id.
