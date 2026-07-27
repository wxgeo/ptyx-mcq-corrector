"""
MCQCheckboxWidget
=================

A PyQt5 widget that:
  1. Displays a scanned MCQ (multiple-choice question) image.
  2. Draws rectangles around detected checkboxes, overlaid on the scan.
  3. Lets the user click a checkbox to toggle its checked / unchecked state,
     redrawing it (color + checkmark) live.
"""

from __future__ import annotations


from PyQt6.QtGui import QColor


from ptyx_mcq_corrector.review.abstract_reviewer import PixReviewer


# --------------------------------------------------------------------------
# The main widget
# --------------------------------------------------------------------------


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
