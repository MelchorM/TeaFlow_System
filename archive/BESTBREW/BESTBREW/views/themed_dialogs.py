from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class ThemedMessageDialog(QDialog):
    def __init__(self, parent, title, message, kind="warning"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(360)

        app = QApplication.instance()
        palette = app.palette() if app else self.palette()

        window_bg = palette.window().color().name()
        text_color = palette.windowText().color().name()
        border_color = palette.mid().color().name()
        button_bg = palette.button().color().name()
        button_text = palette.buttonText().color().name()
        accent = palette.highlight().color().name()
        accent_text = palette.highlightedText().color().name()

        icon_map = {
            "warning": self.style().standardIcon(QStyle.SP_MessageBoxWarning),
            "error": self.style().standardIcon(QStyle.SP_MessageBoxCritical),
            "info": self.style().standardIcon(QStyle.SP_MessageBoxInformation),
        }
        icon = icon_map.get(kind, icon_map["warning"])

        self.setStyleSheet(
            f"""
            QDialog {{
                background: {window_bg};
            }}
            QWidget#dialogCard {{
                background: {window_bg};
                border: 1px solid {border_color};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
                color: {text_color};
                border: none;
            }}
            QLabel#titleLabel {{
                font-size: 20px;
                font-weight: 800;
            }}
            QLabel#messageLabel {{
                font-size: 14px;
                line-height: 1.35em;
            }}
            QLabel#iconBadge {{
                background: {accent};
                border-radius: 24px;
                min-width: 48px;
                max-width: 48px;
                min-height: 48px;
                max-height: 48px;
            }}
            QPushButton#okButton {{
                background: {accent};
                color: {accent_text};
                border: none;
                border-radius: 10px;
                padding: 10px 26px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#okButton:hover {{
                background: {button_bg};
                color: {button_text};
                border: 1px solid {border_color};
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        card = QWidget()
        card.setObjectName("dialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 18)
        card_layout.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(14)

        icon_badge = QLabel()
        icon_badge.setObjectName("iconBadge")
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setPixmap(icon.pixmap(28, 28))

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        title_label.setWordWrap(True)

        message_label = QLabel(message)
        message_label.setObjectName("messageLabel")
        message_label.setWordWrap(True)

        text_wrap.addWidget(title_label)
        text_wrap.addWidget(message_label)

        top.addWidget(icon_badge, 0, Qt.AlignTop)
        top.addLayout(text_wrap, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)

        ok_button = QPushButton("OK")
        ok_button.setObjectName("okButton")
        ok_button.setCursor(Qt.PointingHandCursor)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        actions.addWidget(ok_button)

        card_layout.addLayout(top)
        card_layout.addLayout(actions)
        root.addWidget(card)


def show_themed_message(parent, title, message, kind="warning"):
    dialog = ThemedMessageDialog(parent, title, message, kind=kind)
    return dialog.exec_()
