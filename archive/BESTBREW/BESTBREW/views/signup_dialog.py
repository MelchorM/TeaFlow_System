from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class SignUpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign Up")
        self.resize(420, 220)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Sign up is not available yet.")
        title.setFont(QFont("Times New Roman", 16, QFont.Bold))
        title.setWordWrap(True)

        info = QLabel("Please contact the administrator to create a new account.")
        info.setFont(QFont("Times New Roman", 12))
        info.setWordWrap(True)

        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("Times New Roman", 12, QFont.Bold))
        close_btn.clicked.connect(self.accept)

        layout.addWidget(title)
        layout.addWidget(info)
        layout.addStretch()
        layout.addWidget(close_btn)
