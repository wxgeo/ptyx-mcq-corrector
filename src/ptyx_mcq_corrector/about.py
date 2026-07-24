import sys

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

from importlib.metadata import metadata, PackageNotFoundError

try:
    meta = metadata("mcq-corrector")
    APP_NAME = meta["Name"]
    APP_VERSION = meta["Version"]
except PackageNotFoundError:
    APP_NAME = "MCQ Corrector"
    APP_VERSION = "development"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{APP_NAME}</h2>")
        version = QLabel(f"<b>Application version:</b> {APP_VERSION}")
        pyqt = QLabel(f"<b>PyQt version:</b> {PYQT_VERSION_STR}")
        qt = QLabel(f"<b>Qt version:</b> {QT_VERSION_STR}")
        python = QLabel(
            f"<b>Python version:</b> "
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(10)
        layout.addWidget(pyqt)
        layout.addWidget(qt)
        layout.addWidget(python)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addSpacing(15)
        layout.addWidget(buttons)
