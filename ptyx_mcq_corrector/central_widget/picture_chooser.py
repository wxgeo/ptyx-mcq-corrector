from pathlib import Path

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QComboBox, QLabel, QHBoxLayout, QVBoxLayout


class ImageDisplayWindow(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        # Create the combo box for selecting an image
        self.comboBox = QComboBox(self)
        self.comboBox.addItem("Image 1")
        self.comboBox.addItem("Image 2")

        # Connect the combo box selection change to a method
        self.comboBox.currentIndexChanged.connect(self.select_image)

        # Create labels for the images
        self.label1 = QLabel(self)
        self.label2 = QLabel(self)

        # Create a horizontal layout for the images
        hbox = QHBoxLayout()
        hbox.addWidget(self.label1)
        hbox.addWidget(self.label2)

        # Create a vertical layout and add the combo box and image labels
        vbox = QVBoxLayout()
        vbox.addWidget(self.comboBox)
        vbox.addLayout(hbox)

        # Set the layout for the window
        self.setLayout(vbox)

        # Set the window title and size
        self.setWindowTitle("Select Image to Display")

    def set_images(self, path1: Path, path2: Path):
        """Load the images."""
        self.label1.setPixmap(QPixmap(path1))
        self.label2.setPixmap(QPixmap(path2))

    # Method to update the images based on combo box selection
    def update_images(self, index: int) -> None:
        if index == 0:
            self.label1.setPixmap(self.pixmap1)
            self.label2.setPixmap(self.pixmap1)
        else:
            self.label1.setPixmap(self.pixmap2)
            self.label2.setPixmap(self.pixmap2)
