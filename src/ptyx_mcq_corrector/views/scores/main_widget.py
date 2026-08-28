"""
Student viewer built on top of the generic CollapsibleSidebar widget.

- Left: CollapsibleSidebar("Students", <QListWidget of student names>)
- Main area: two QLabels on top (left/right) + a widget below that
  shows either a PDF or a "Loading..." placeholder

Optional dependency: PyQt6-QPdf (for actual PDF rendering)
    pip install PyQt6 PyQt6-QPdf
"""

from pathlib import Path
from statistics import mean
from typing import Iterable

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
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

from ptyx_mcq.scan.data.documents import Document
from ptyx_mcq.scan.data.students import Student
from ptyx_mcq.tools.parse_config.subtypes import DocumentId

from ptyx_mcq_corrector.app_state import STATE
from ptyx_mcq_corrector.custom_widgets.generic.collapsible_sidebar import CollapsibleSidebar

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
        self.loading_label = QLabel("")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 18px; color: gray;")
        self.addWidget(self.loading_label)

        # Page 1: PDF viewer (or fallback placeholder if QtPdf isn't installed)
        if PDF_SUPPORT:
            self.pdf_document = QPdfDocument(self)
            self.pdf_view = QPdfView(self)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.pdf_view.setDocument(self.pdf_document)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.addWidget(self.pdf_view)
        else:
            self.pdf_view = QLabel("PDF support not installed.\nRun: pip install PyQt6-QPdf")
            self.pdf_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.addWidget(self.pdf_view)

        self.setCurrentIndex(0)  # start on "Loading..."

    def show_loading(self, text=""):
        self.loading_label.setText(text)
        self.setCurrentIndex(0)

    def show_pdf(self, path: Path | str) -> None:
        if PDF_SUPPORT:
            self.pdf_document.load(str(path))
        self.setCurrentIndex(1)

    def ask_for_pdf(self, doc: Document) -> None:
        if not (path := doc.correction_path).is_file():
            STATE.corrections_manager.generate_doc_now(doc)
        else:
            self.show_pdf(path)


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
        self.label_center = QLabel("")
        self.label_right = QLabel("")
        # self.label_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # top_row.addWidget(self.label_left)
        # top_row.addWidget(QWidget(self), stretch=1)
        # top_row.addWidget(self.label_center)
        # top_row.addWidget(QWidget(self), stretch=1)
        # top_row.addWidget(self.label_right)
        self.label_left.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label_center.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.label_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top_row.addWidget(self.label_left, 1)
        top_row.addWidget(self.label_center, 1)
        top_row.addWidget(self.label_right, 1)
        main_layout.addLayout(top_row)

        self.pdf_or_loading = PdfOrLoadingWidget()
        main_layout.addWidget(self.pdf_or_loading)

        root_layout.addWidget(main_area, stretch=1)

        self.students_list.currentTextChanged.connect(self.on_student_selected)
        STATE.corrections_manager.docs_generator.document_ready.connect(self.on_document_ready)

    def on_student_selected(self, name: str):
        if not name:
            return
        student = Student.from_text(name)
        self.label_left.setText(f"Student: <b>{student.name}</b>")
        scores = STATE.scores
        assert scores is not None
        values: list[float] = [value for value in scores.values() if isinstance(value, (float, int))]
        min_score: float | str = min(values, default="")
        max_score: float | str = max(values, default="")
        mean_score: float | str = mean(values) if values else ""

        def fmt(v: float | str) -> str:
            return v if isinstance(v, str) else str(round(v, 2))

        self.label_right.setText(
            f"<i>Min:</i> <span style='color:darkred'>{fmt(min_score)}</span> "
            f"• <i>Max:</i> <span style='color:darkgreen'>{fmt(max_score)}</span> "
            f"• <i>Mean:</i> <span style='color:cornflowerblue'>{fmt(mean_score)}</span>"
        )
        self._display_score(student)
        assert STATE.parser is not None
        doc = STATE.parser.scan_data.get_student_doc(student)
        if doc is not None:
            self.pdf_or_loading.ask_for_pdf(doc)

    @property
    def current_student(self) -> Student | None:
        selected_item = self.students_list.currentItem()
        if selected_item is None:
            return None
        return Student.from_text(selected_item.text())

    def on_document_ready(
        self,
        doc_id: DocumentId,
        answer: object,
    ):
        assert STATE.parser is not None
        doc = STATE.parser.scan_data.used_docs_index[doc_id]
        if doc.student == self.current_student:
            # The pdf is ready to be displayed now.
            self.pdf_or_loading.ask_for_pdf(doc)

    def _display_score(self, student: Student) -> None:
        scores = STATE.scores
        assert scores is not None
        score = scores[student]
        parser = STATE.parser
        assert parser is not None
        has_score = not isinstance(score, str)
        if has_score:
            color = "cornflowerblue"
            lighter = QColor(color).lighter(150).name()
            if isinstance(score, float):
                score = round(score, 2)
            max_score = parser.scores_manager.max_score
            formatted_score = f"<b style='color:cornflowerblue'>{score:g}</b> / {max_score:g}"
        else:
            color = "darkred"
            lighter = QColor(color).lighter(300).name()
            formatted_score = f"<b style='color: darkred'>{score}</b> "

        self.label_center.setText(f"<i>Score:</i> {formatted_score}")
        self.label_center.setStyleSheet(
            f"QLabel{{margin:auto;background:{lighter};padding:5px;border:2px solid {color};border-radius: 9px;}}"
        )
        font = self.label_center.font()
        font.setPointSize(self.label_left.font().pointSize() + 2)  # bump up by 2pt
        self.label_center.setFont(font)

        # Show the loading state first (simulate a lookup / fetch)
        self.pdf_or_loading.show_loading("Loading..." if has_score else "")

        # --- Replace this with your real logic ---
        # e.g. look up the PDF path for this student, then call:
        #   self.pdf_or_loading.show_pdf("/path/to/student.pdf")
        #   self.label_center.setText("Status: Loaded")
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
