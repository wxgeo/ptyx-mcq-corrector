from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSpacerItem, QSizePolicy, QLabel


class DefaultView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        horizontal = QHBoxLayout()
        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        horizontal.addSpacerItem(spacer)
        self.header_label = QLabel(parent=self)
        self.header_label.setTextFormat(Qt.TextFormat.RichText)
        self.header_label.setOpenExternalLinks(True)
        self.header_label.setObjectName("header_label")
        horizontal.addWidget(self.header_label)
        spacer2 = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        horizontal.addSpacerItem(spacer2)
        main_layout.addLayout(horizontal)
        spacer3 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addSpacerItem(spacer3)
