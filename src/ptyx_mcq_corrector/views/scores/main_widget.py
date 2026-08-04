"""
Student viewer built on top of the generic CollapsibleSidebar widget.

- Left: CollapsibleSidebar("Students", <QListWidget of student names>)
- Main area: two QLabels on top (left/right) + a widget below that
  shows either a PDF or a "Loading..." placeholder

Optional dependency: PyQt6-QPdf (for actual PDF rendering)
    pip install PyQt6 PyQt6-QPdf
"""

from typing import Iterable

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QSizePolicy,
)

from ptyx_mcq.scan.data.students import Student
from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.collapsible_sidebar import CollapsibleSidebar

# Try to import PDF viewing support (optional)
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class PdfOrLoadingWidget(QStackedWidget):
    """Stacked widget with two pages: 'loading' and 'pdf'."""

    def __init__(self):
        super().__init__()

        # Page 0: Loading placeholder
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 18px; color: gray;")
        self.addWidget(self.loading_label)

        # Page 1: PDF viewer (or fallback placeholder if QtPdf isn't installed)
        if PDF_SUPPORT:
            self.pdf_document = QPdfDocument(self)
            self.pdf_view = QPdfView(self)
            self.pdf_view.setDocument(self.pdf_document)
            self.addWidget(self.pdf_view)
        else:
            self.pdf_view = QLabel("PDF support not installed.\nRun: pip install PyQt6-QPdf")
            self.pdf_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addWidget(self.pdf_view)

        self.setCurrentIndex(0)  # start on "Loading..."

    def show_loading(self):
        self.setCurrentIndex(0)

    def show_pdf(self, path: str):
        if PDF_SUPPORT:
            self.pdf_document.load(path)
        self.setCurrentIndex(1)


class StudentsWidget(QListWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

    def sizeHint(self) -> QSize:
        size = super().sizeHint()
        bar = self.verticalScrollBar()
        assert bar is not None
        width = self.sizeHintForColumn(0) + 2 * self.frameWidth() + bar.sizeHint().width()
        return QSize(max(size.width(), width), size.height())


class ScoresView(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root_layout = QHBoxLayout(self)
        self.students_list = StudentsWidget(self)
        # --- Left: generic sidebar, filled with a student list ---
        self.sidebar = CollapsibleSidebar("Students", self.students_list, parent=self)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # self.students_list.setParent(self.sidebar)
        root_layout.addWidget(self.sidebar)

        # --- Main area ---
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)

        top_row = QHBoxLayout()
        self.label_left = QLabel("No student selected")
        self.label_right = QLabel("")
        self.label_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.label_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.label_right.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_row.addWidget(self.label_left)
        top_row.addWidget(self.label_right)
        main_layout.addLayout(top_row)

        self.pdf_or_loading = PdfOrLoadingWidget()
        main_layout.addWidget(self.pdf_or_loading)

        root_layout.addWidget(main_area, stretch=1)

        self.students_list.currentTextChanged.connect(self.on_student_selected)

    def on_student_selected(self, name: str):
        if not name:
            return
        self.label_left.setText(f"Student: {name}")
        self.label_right.setText("Status: Loading")

        # Show the loading state first (simulate a lookup / fetch)
        self.pdf_or_loading.show_loading()

        # --- Replace this with your real logic ---
        # e.g. look up the PDF path for this student, then call:
        #   self.pdf_or_loading.show_pdf("/path/to/student.pdf")
        #   self.label_right.setText("Status: Loaded")
        #
        # For demo purposes we just leave it on "Loading..." since
        # there is no real file to load here.

    def udpdate_students_list(self):
        self._update_students_list(STATE.scores)
        self.sidebar.update_width()

    def _update_students_list(self, students: Iterable[Student]):
        """Replace all items in list_widget without firing currentTextChanged mid-update."""
        _list = self.students_list
        try:
            _list.blockSignals(True)
            _list.clear()
            for student in students:
                QListWidgetItem(student.to_text(), _list)
        finally:
            _list.blockSignals(False)
