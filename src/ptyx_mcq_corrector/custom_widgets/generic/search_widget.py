from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QLineEdit,
    QToolButton,
    QCheckBox,
    QHBoxLayout,
    QFrame,
    QSizePolicy,
    QVBoxLayout,
)


class SearchWidget(QWidget):
    """
    A compact search box:
      [ QLineEdit .................. ] [v]
        (hidden by default) case-sensitive / regex checkboxes
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- line edit -------------------------------------------------
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Search…")

        # --- toggle button (arrow) -------------------------------------
        self.toggle_button = QToolButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setFixedWidth(18)
        self.toggle_button.setToolTip("Show search options")
        self.toggle_button.clicked.connect(self._on_toggle)

        # --- checkboxes (options row) -----------------------------------
        self.case_checkbox = QCheckBox("Case sensitive")
        self.regex_checkbox = QCheckBox("Regex")

        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(4, 0, 0, 0)
        options_layout.setSpacing(10)
        options_layout.addWidget(self.case_checkbox)
        options_layout.addWidget(self.regex_checkbox)
        options_layout.addStretch()

        # Wrap options in a frame so we can hide/show it as one unit,
        # and so it takes zero height when collapsed.
        self.options_frame = QFrame()
        self.options_frame.setLayout(options_layout)
        self.options_frame.setVisible(False)
        self.options_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # --- top row: line edit + toggle --------------------------------
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(2)
        top_row.addWidget(self.line_edit)
        top_row.addWidget(self.toggle_button)

        # --- main layout --------------------------------------------------
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        main_layout.addLayout(top_row)
        main_layout.addWidget(self.options_frame)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _on_toggle(self, checked: bool):
        self.options_frame.setVisible(checked)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.toggle_button.setToolTip("Hide search options" if checked else "Show search options")

    # --- convenience accessors -----------------------------------------
    def text(self) -> str:
        return self.line_edit.text()

    @property
    def is_case_sensitive(self) -> bool:
        return self.case_checkbox.isChecked()

    @property
    def is_regex(self) -> bool:
        return self.regex_checkbox.isChecked()
