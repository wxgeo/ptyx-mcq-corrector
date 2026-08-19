from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout

from ptyx_mcq_corrector.app_state import STATE


class IntegrityView(QWidget):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent)
        main_layout = QHBoxLayout(self)
        self.info = QLabel()
        main_layout.addWidget(self.info, alignment=Qt.AlignmentFlag.AlignTop)

    def update_issues(self):
        html: list[str] = ["<h1 style='color: darkred;'>Errors</h1>"]
        categories = {
            "⚠ Missing": (STATE.integrity_issues.missing_pages, "not found."),
            "⚠ Duplicates": (STATE.integrity_issues.duplicates, "found in different versions."),
        }

        for title, (issues, msg) in categories.items():
            if issues:
                html.append(f"<h2>{title} pages</h2><ul>")
                for doc_id, pages in issues.items():
                    html.append(
                        f"<li><strong>Document {doc_id}:</strong> pages {', '.join(map(str, pages))} {msg}</li>"
                    )
                html.append("</ul>")
        html.append("<p style='border: 1px solid blue'>Please fix the scanned documents and retry.</p>")
        self.info.setText("\n".join(html))
