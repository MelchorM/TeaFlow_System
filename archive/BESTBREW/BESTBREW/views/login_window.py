import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QDialog
)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QPen, QColor, QIcon
from PyQt5.QtCore import Qt, QPointF, QSize
from controllers.auth_controller import AuthController
from controllers.dashboard_controller import DashboardController
from views.themed_dialogs import show_themed_message

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
WELCOME_WORDMARK_PATH = os.path.join(PROJECT_ROOT, "assets", "welcome_wordmark.png")


def portable_fixed_window_mode():
    return str(os.getenv("BESTBREW_FIXED_WINDOW", "")).strip().lower() in {"1", "true", "yes", "on"}


def password_eye_icon(closed=False, size=22, color="#4e3427"):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidth(2)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    w = float(size)
    h = float(size)
    left = QPointF(w * 0.12, h * 0.5)
    top = QPointF(w * 0.5, h * 0.2)
    right = QPointF(w * 0.88, h * 0.5)
    bottom = QPointF(w * 0.5, h * 0.8)

    painter.drawLine(left, top)
    painter.drawLine(top, right)
    painter.drawLine(right, bottom)
    painter.drawLine(bottom, left)

    if closed:
        painter.drawLine(QPointF(w * 0.2, h * 0.8), QPointF(w * 0.8, h * 0.2))
    else:
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(w * 0.5, h * 0.5), w * 0.12, h * 0.12)

    painter.end()
    return QIcon(pixmap)


def tinted_pixmap(image_path, color="#ffffff", max_width=280, max_height=92, crop_left=0):
    if not os.path.exists(image_path):
        return QPixmap()

    source = QPixmap(image_path)
    if source.isNull():
        return QPixmap()

    if crop_left > 0 and crop_left < source.width():
        source = source.copy(crop_left, 0, source.width() - crop_left, source.height())

    scaled = source.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    tinted = QPixmap(scaled.size())
    tinted.fill(Qt.transparent)

    painter = QPainter(tinted)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawPixmap(0, 0, scaled)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    return tinted


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Password")
        self.setModal(True)
        self.setFixedSize(560, 410)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog {
                background:#fff8f1;
                border:1px solid #dfc2ab;
                border-radius:26px;
            }
            QLabel {
                background:transparent;
                color:#241610;
                border:none;
            }
            QLineEdit {
                background:#fffdfa;
                border:1px solid #dfc2ab;
                border-radius:14px;
                padding:16px 18px;
                font-size:17px;
                color:#2b1b14;
                min-height:30px;
            }
            QPushButton#primary {
                background:#8b5638;
                color:white;
                border:none;
                border-radius:14px;
                padding:16px 18px;
                font-size:17px;
                font-weight:900;
                min-height:26px;
            }
            QPushButton#secondary {
                background:#fffdfa;
                color:#7b4d32;
                border:1px solid #dfc2ab;
                border-radius:14px;
                padding:16px 18px;
                font-size:17px;
                font-weight:900;
                min-height:26px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 28)
        root.setSpacing(16)

        title = QLabel("Forgot Password")
        title.setFont(QFont("Times New Roman", 28, QFont.Bold))
        root.addWidget(title)

        subtitle = QLabel("Enter the username and set a new password.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size:16px; color:#8c796d;")
        root.addWidget(subtitle)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        root.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("New Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        root.addWidget(self.password_input)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm New Password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        root.addWidget(self.confirm_password_input)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet("font-size:14px; color:#b04444; font-weight:700;")
        root.addWidget(self.msg)

        root.addStretch()

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Reset Password")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        root.addLayout(actions)

    def values(self):
        return (
            self.username_input.text().strip(),
            self.password_input.text().strip(),
            self.confirm_password_input.text().strip(),
        )


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.auth_controller = AuthController()
        self.setWindowTitle("Best Brew - Login")
        self.setMinimumSize(1200, 760)
        self.resize(1400, 850)

        self.admin_window = None
        self.build_ui()
        if portable_fixed_window_mode():
            self.show()
        else:
            self.showMaximized()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self.bg = QLabel()
        self.bg.setScaledContents(True)
        self.bg.setStyleSheet("background:#4e3427;")
        root.addWidget(self.bg)

        bg_path = os.path.join(PROJECT_ROOT, "assets", "login_bg.jpg")
        if os.path.exists(bg_path):
            pix = QPixmap(bg_path)
            if not pix.isNull():
                self.bg.setPixmap(pix)

        self.dark_overlay = QWidget(central)
        self.dark_overlay.setStyleSheet("background: rgba(0, 0, 0, 0.25);")

        self.overlay = QWidget(central)
        self.overlay.setAttribute(Qt.WA_TranslucentBackground)

        wrap = QHBoxLayout(self.overlay)
        wrap.setContentsMargins(70, 50, 70, 50)
        wrap.setSpacing(40)

        wrap.addWidget(self.build_left_brand(), 1)
        wrap.addWidget(self.build_login_card(), 1, alignment=Qt.AlignCenter)

        self.dark_overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.dark_overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setGeometry(0, 0, self.width(), self.height())

    def build_left_brand(self):
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 40, 20, 40)
        layout.setSpacing(18)
        layout.addStretch()

        title = QLabel("Best Brew")
        title.setFont(QFont("Times New Roman", 42, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")

        subtitle = QLabel("Sip. Drink. Enjoy.")
        subtitle.setFont(QFont("Times New Roman", 20, QFont.Bold))
        subtitle.setStyleSheet("color: #f6f1eb; background: transparent;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

        return panel

    def build_login_card(self):
        card = QFrame()
        card.setFixedWidth(520)
        card.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.14);
                border: none;
                border-radius: 28px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(18)

        center_title = QLabel()
        center_title.setAlignment(Qt.AlignCenter)
        center_title.setStyleSheet("color: white; background: transparent;")
        welcome_pix = tinted_pixmap(WELCOME_WORDMARK_PATH, "#ffffff", 400, 132, crop_left=28)
        if not welcome_pix.isNull():
            center_title.setPixmap(welcome_pix)
        else:
            center_title.setText("Welcome")
            center_title.setFont(QFont("Times New Roman", 42, QFont.Bold))
        layout.addWidget(center_title)

        self.uname = QLineEdit()
        self.uname.setPlaceholderText("Username")
        self.uname.setFixedHeight(56)
        self.uname.setFont(QFont("Times New Roman", 12))
        self.uname.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.96);
                border: none;
                border-radius: 12px;
                padding: 0 18px;
                color: #222;
            }
            QLineEdit::placeholder {
                color: #777;
            }
        """)
        self.uname.returnPressed.connect(self.login)
        layout.addWidget(self.uname)

        password_wrap = QWidget()
        password_wrap.setStyleSheet("background: transparent;")
        password_row = QHBoxLayout(password_wrap)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(10)

        self.pword = QLineEdit()
        self.pword.setPlaceholderText("Password")
        self.pword.setEchoMode(QLineEdit.Password)
        self.pword.setFixedHeight(56)
        self.pword.setFont(QFont("Times New Roman", 12))
        self.pword.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.96);
                border: none;
                border-radius: 12px;
                padding: 0 18px;
                color: #222;
            }
            QLineEdit::placeholder {
                color: #777;
            }
        """)
        self.pword.returnPressed.connect(self.login)
        password_row.addWidget(self.pword, 1)

        self.password_toggle_btn = QPushButton("")
        self.password_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.password_toggle_btn.setFixedSize(52, 44)
        self.password_toggle_btn.setFont(QFont("Times New Roman", 11, QFont.Bold))
        self.password_toggle_btn.setIcon(password_eye_icon(closed=True))
        self.password_toggle_btn.setIconSize(QSize(22, 22))
        self.password_toggle_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.92);
                color: #4e3427;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: white;
            }
        """)
        self.password_toggle_btn.clicked.connect(self.toggle_password_visibility)
        password_row.addWidget(self.password_toggle_btn)
        layout.addWidget(password_wrap)

        forgot = QPushButton("Forgot Password?")
        forgot.setFlat(True)
        forgot.setCursor(Qt.PointingHandCursor)
        forgot.setFont(QFont("Times New Roman", 12))
        forgot.setStyleSheet("""
            QPushButton {
                color: #f3f3f3;
                text-align: left;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                color: white;
                text-decoration: underline;
            }
        """)
        forgot.clicked.connect(self.open_forgot_password_dialog)
        layout.addWidget(forgot, alignment=Qt.AlignLeft)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn = QPushButton("Log In")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setFixedSize(160, 52)
        self.btn.setFont(QFont("Times New Roman", 13, QFont.Bold))
        self.btn.setStyleSheet("""
            QPushButton {
                background: #f3f3f3;
                color: #1f1f1f;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: white;
            }
        """)
        self.btn.clicked.connect(self.login)
        btn_row.addWidget(self.btn)
        layout.addLayout(btn_row)

        self.msg = QLabel("")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setFont(QFont("Times New Roman", 11, QFont.Bold))
        self.msg.setStyleSheet("color: #ffd7d7; background: transparent;")
        layout.addWidget(self.msg)

        return card

    def login(self):
        username = self.uname.text().strip()
        password = self.pword.text().strip()

        user = self.auth_controller.authenticate(username, password)

        if user:
            self.open_dashboard_for_user(user)
        else:
            self.msg.setText("Invalid username or password.")
            self.pword.clear()

    def toggle_password_visibility(self):
        is_hidden = self.pword.echoMode() == QLineEdit.Password
        self.pword.setEchoMode(QLineEdit.Normal if is_hidden else QLineEdit.Password)
        self.password_toggle_btn.setIcon(password_eye_icon(closed=not is_hidden))

    def open_forgot_password_dialog(self):
        dialog = ForgotPasswordDialog(self)
        if self.uname.text().strip():
            dialog.username_input.setText(self.uname.text().strip())
        if dialog.exec_() != QDialog.Accepted:
            return

        username, new_password, confirm_password = dialog.values()
        if not username:
            show_themed_message(self, "Reset Password", "Please enter the username.", "warning")
            return
        if not new_password:
            show_themed_message(self, "Reset Password", "Please enter the new password.", "warning")
            return
        if new_password != confirm_password:
            show_themed_message(self, "Reset Password", "New password and confirm password do not match.", "warning")
            return
        try:
            self.auth_controller.reset_password(username, new_password)
            self.msg.setStyleSheet("color: #d7ffd7; background: transparent;")
            self.msg.setText("Password reset successful. You can log in now.")
            self.uname.setText(username)
            self.pword.clear()
        except Exception as e:
            self.msg.setStyleSheet("color: #ffd7d7; background: transparent;")
            show_themed_message(self, "Reset Password", str(e), "warning")

    def open_dashboard_for_user(self, user=None):
        role = str((user or {}).get("role", "admin")).strip().lower()
        if role == "cashier":
            from views.cashier_dashboard_view import CashierDashboardView
            self.admin_window = CashierDashboardView(user=user, login_window=self, controller=DashboardController())
        else:
            from views.dashboard_view import AdminDashboardView
            self.admin_window = AdminDashboardView(user=user, login_window=self, controller=DashboardController())
        if portable_fixed_window_mode():
            self.admin_window.show()
        else:
            self.admin_window.showMaximized()
        self.hide()
