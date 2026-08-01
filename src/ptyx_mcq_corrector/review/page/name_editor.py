"""
MCQCheckboxWidget
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Draws rectangles around detected checkboxes, overlaid on the scan.
  3. Lets the user click a checkbox to toggle its checked / unchecked state,
     redrawing it (color + checkmark) live.
"""

import os
from enum import Enum
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QLineEdit, QLabel, QHBoxLayout, QCompleter
from PyQt6.QtCore import QEvent, QObject, QTimer


from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.tools.parse_config.subtypes import StudentName, StudentId

from ptyx_mcq_corrector.internal_state import STATE
from ptyx_mcq_corrector.review.page.page_displayer import PageDisplayer

if TYPE_CHECKING:
    from ptyx_mcq_corrector.review.page.page_reviewer import PageReviewer


# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


def student_to_text(student: Student) -> str:
    if student.name:
        return f"{student.name} ({student.id})"
    return student.id


def student_from_text(text: str) -> Student:
    match text.split("("):
        case name, id_:
            assert name.endswith(" ")
            assert id_.endswith(")")
            return Student(name=StudentName(name[:-1]), id=StudentId(id_[:-1]))
        case _:
            raise ValueError(f"Invalid student name: {text}")


class NameStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"


class PopupHideFilter(QObject):
    """Fix a bug on WSL, since .setVisible(False) does not work there for QCompleter.popup()."""

    def eventFilter(self, obj, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Hide:
            QTimer.singleShot(0, lambda: self._destroy_native(obj))
        return False

    @staticmethod
    def _destroy_native(widget: QWidget):
        handle = widget.windowHandle()
        if handle is not None:
            handle.destroy()


class NameEditor(QWidget):
    # name_changed = pyqtSignal(str, name="name_changed")

    _styles = {
        NameStatus.VALID: "QLineEdit { margin-left: 10px;background-color: #c5fcac;} QLabel {color: green;}",
        NameStatus.INVALID: "QLineEdit { margin-left: 10px;background-color: #fcb1ac;} QLabel {color: red;}",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent: "PageReviewer" = parent  # type: ignore
        self.name_editor = QLineEdit(self)
        # self.name_editor.setStyleSheet("QLineEdit { margin-left: 10px;}")
        label = QLabel("&Name/Id:")
        # label.setStyleSheet("QLabel {color: red;}")
        self.display_as(NameStatus.INVALID)
        label.setBuddy(self.name_editor)
        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.name_editor.setCompleter(self.completer)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        layout.addWidget(self.name_editor)

        self.name_editor.textChanged.connect(self.on_text_changed)
        # self.completer.activated.connect(lambda: _force_close(self.completer))
        if "WSL_DISTRO_NAME" in os.environ:
            # Fix a bug on WSL, since .setVisible(False) does not work there for QCompleter.popup().
            # (It leaves a stale window behind).
            self._hide_filter = PopupHideFilter(self)
            popup = self.completer.popup()
            assert popup is not None
            popup.installEventFilter(self._hide_filter)
            # Note: if the QCompleter popup should be ever recreated, be careful to reinstall this event filter.

    def display_as(self, status: NameStatus) -> None:
        self.setStyleSheet(self._styles[status])

    def on_text_changed(self, text: str) -> None:
        # self.name_changed.emit(text)
        if text in self.names_suggestions:
            self._parent.page.pic.student = student_from_text(text)
            self.display_as(NameStatus.VALID)
        else:
            self.display_as(NameStatus.INVALID)

    @property
    def names_suggestions(self) -> list[str]:
        return sorted([student_to_text(student) for student in STATE.students])

    def update_suggestions(self):
        model = QStringListModel(self.names_suggestions, self)
        self.completer.setModel(model)

    def set_current_student(self, student: Student | None) -> None:
        self.name_editor.setText("" if student is None else student_to_text(student))

    # def keyPressEvent(self, event):
    #     if event.key() == Qt.Key.Key_Escape:
    #         self.main_window.issuesView.setFocus()
    #     else:
    #         super().keyPressEvent(event)


class NameReviewer(PageDisplayer):
    """Displays a scanned MCQ image with overlaid, clickable checkbox rectangles."""

    # _student: Student

    FOCUS_RECT_COLOR: QColor = QColor("magenta")
    #
    # def reset(self) -> None:
    #     super().reset()
    # self._student = Student(name=StudentName(""), id=StudentId(""))

    # ---- public API ----------------------------------------------------

    # def _on_page_set(self) -> None:
    #     if (page := self.page) is not None:
    #         self._student = page.student

    # def validate(self) -> None:
    #     """Save the new student's name and id on the drive."""
    #     if (page := self.page) is not None:
    #         self.page.pic.student = self._student
