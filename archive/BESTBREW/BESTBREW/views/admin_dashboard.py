import base64
import html
import json
import math
import os
import shutil
import sys
from uuid import uuid4
from datetime import date
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QGridLayout,
    QLineEdit, QScrollArea, QDialog, QTextEdit,
    QSpinBox, QFileDialog, QTableWidget, QTableWidgetItem, QComboBox,
    QCheckBox, QMenu,
    QHeaderView, QSizePolicy, QStyle
)
from PyQt5.QtCore import Qt, QDateTime, QTimer, QSize, QPointF, QRectF, QTime, QSizeF, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QColor, QPen, QPolygonF, QTextDocument, QPageLayout, QPageSize, QImage, QAbstractTextDocumentLayout
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from controllers.dashboard_controller import DashboardController
from models import db as database
from views.themed_dialogs import show_themed_message

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
PRODUCT_IMAGE_DIR = os.path.join(PROJECT_ROOT, "assets", "products")


def ensure_product_image_dir():
    os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
    return PRODUCT_IMAGE_DIR


def portable_fixed_window_mode():
    return str(os.getenv("BESTBREW_FIXED_WINDOW", "")).strip().lower() in {"1", "true", "yes", "on"}


def project_relative_path(path):
    if not path:
        return ""
    return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")


def resolve_product_image_path(stored_path):
    if not stored_path:
        return ""

    normalized = os.path.normpath(str(stored_path))
    candidates = []

    if os.path.isabs(normalized):
        candidates.append(normalized)

        path_parts = normalized.split(os.sep)
        if "assets" in path_parts:
            assets_index = path_parts.index("assets")
            candidates.append(os.path.join(PROJECT_ROOT, *path_parts[assets_index:]))
    else:
        candidates.append(os.path.join(PROJECT_ROOT, normalized))

    candidates.append(os.path.join(PRODUCT_IMAGE_DIR, os.path.basename(normalized)))

    seen = set()
    for candidate in candidates:
        absolute_candidate = os.path.abspath(candidate)
        if absolute_candidate in seen:
            continue
        seen.add(absolute_candidate)
        if os.path.exists(absolute_candidate):
            return absolute_candidate

    return normalized if os.path.isabs(normalized) else os.path.join(PROJECT_ROOT, normalized)


def import_product_image(source_path):
    if not source_path:
        return ""

    resolved_source = resolve_product_image_path(source_path)
    if not os.path.exists(resolved_source):
        return source_path

    absolute_source = os.path.abspath(resolved_source)
    absolute_root = os.path.abspath(PROJECT_ROOT)

    if os.path.commonpath([absolute_source, absolute_root]) == absolute_root:
        return project_relative_path(absolute_source)

    ensure_product_image_dir()
    base_name = os.path.basename(absolute_source)
    stem, ext = os.path.splitext(base_name)
    safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem).strip("_") or "product"
    destination_name = f"{safe_stem}_{uuid4().hex[:8]}{ext.lower()}"
    destination_path = os.path.join(PRODUCT_IMAGE_DIR, destination_name)
    shutil.copy2(absolute_source, destination_path)
    return project_relative_path(destination_path)


def build_unique_export_path(export_dir, prefix, summary_date, extension):
    timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss_zzz")
    base_name = f"{prefix}_{summary_date}_{timestamp}{extension}"
    export_path = os.path.join(export_dir, base_name)

    if not os.path.exists(export_path):
        return export_path

    fallback_name = f"{prefix}_{summary_date}_{timestamp}_{uuid4().hex[:6]}{extension}"
    return os.path.join(export_dir, fallback_name)


class RevenueChartWidget(QWidget):
    def __init__(self, labels=None, values=None, parent=None):
        super().__init__(parent)
        self.labels = labels or ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self.values = values or [40, 70, 120, 180, 220, 130, 50]
        self.setMinimumHeight(220)
        self.setMaximumHeight(220)

    def paintEvent(self, event):
        if not self.values:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(50, 18, -18, -38)
        grid_pen = QPen(QColor("#f0dfcf"), 1)
        axis_pen = QPen(QColor("#dcc1aa"), 1.2)
        line_pen = QPen(QColor("#bc6d35"), 3)

        max_value = max(max(self.values), 300)
        y_steps = [0, 100, 200, 300]

        painter.setPen(grid_pen)
        for step in y_steps:
            y = rect.bottom() - (step / max_value) * rect.height()
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        painter.setPen(axis_pen)
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        step_x = rect.width() / max(1, len(self.values) - 1)
        points = []
        for index, value in enumerate(self.values):
            x = rect.left() + index * step_x
            y = rect.bottom() - (value / max_value) * rect.height()
            points.append((x, y))

        painter.setBrush(QColor(188, 109, 53, 34))
        painter.setPen(Qt.NoPen)
        fill_points = [QPointF(points[0][0], rect.bottom())]
        fill_points.extend(QPointF(x, y) for x, y in points)
        fill_points.append(QPointF(points[-1][0], rect.bottom()))
        painter.drawPolygon(QPolygonF(fill_points))

        painter.setPen(line_pen)
        for index in range(len(points) - 1):
            painter.drawLine(
                int(points[index][0]), int(points[index][1]),
                int(points[index + 1][0]), int(points[index + 1][1])
            )

        painter.setBrush(QColor("#bc6d35"))
        painter.setPen(QPen(QColor("#fff9f3"), 2))
        for x, y in points:
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

        painter.setPen(QColor("#9e816b"))
        for step in y_steps:
            y = rect.bottom() - (step / max_value) * rect.height()
            painter.drawText(6, int(y + 5), f"\u20b1{step}")

        for index, label in enumerate(self.labels):
            x = rect.left() + index * step_x
            painter.drawText(int(x - 8), rect.bottom() + 26, label)


class DonutChartWidget(QWidget):
    def __init__(self, values=None, colors=None, center_top="13", center_bottom="Total Items", parent=None):
        super().__init__(parent)
        self.values = values or [6, 7, 0]
        self.colors = colors or ["#8ca55a", "#eb9b45", "#d7493b"]
        self.center_top = center_top
        self.center_bottom = center_bottom
        self.setMinimumSize(186, 186)
        self.setMaximumSize(186, 186)

    def paintEvent(self, event):
        total = sum(self.values)
        if total <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = self.rect().adjusted(20, 20, -20, -20)
        pen = QPen()
        pen.setWidth(22)
        start_angle = 90 * 16

        for value, color in zip(self.values, self.colors):
            span_angle = -int((value / total) * 360 * 16)
            pen.setColor(QColor(color))
            painter.setPen(pen)
            painter.drawArc(outer, start_angle, span_angle)
            start_angle += span_angle

        inner = outer.adjusted(38, 38, -38, -38)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#fffdf9"))
        painter.drawEllipse(inner)

        show_bottom_label = bool(str(self.center_bottom).strip())
        if show_bottom_label:
            number_rect = inner.adjusted(0, -8, 0, -6)
            label_rect = inner.adjusted(6, 28, -6, 0)
        else:
            number_rect = inner
            label_rect = inner

        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#251a14"))
        painter.drawText(number_rect, Qt.AlignHCenter | Qt.AlignVCenter, self.center_top)

        if show_bottom_label:
            font.setPointSize(11)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#7b6e66"))
            painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.center_bottom)


class ProductBarChartWidget(QWidget):
    def __init__(self, products=None, parent=None):
        super().__init__(parent)
        self.products = products or []
        self.palette_colors = ["#b56c35", "#efa62f", "#9f7cc5", "#9fbe63", "#ef9d86", "#c87965"]
        self.setMinimumHeight(270)
        self.setMaximumHeight(270)

    def paintEvent(self, event):
        if not self.products:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(58, 16, -18, -54)
        max_value = max([product.get("revenue", 0) for product in self.products] + [250])
        steps = [0, 50, 100, 150, 200, 250]

        painter.setPen(QPen(QColor("#f0dfcf"), 1))
        for step in steps:
            y = rect.bottom() - (step / max_value) * rect.height()
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        painter.setPen(QPen(QColor("#ddc2ad"), 1.2))
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        count = max(1, len(self.products))
        slot_width = rect.width() / count
        bar_width = min(104, slot_width * 0.62)

        for index, product in enumerate(self.products):
            revenue = max(0, int(product.get("revenue", 0)))
            label = str(product.get("name", "Product"))
            short_label = label if len(label) <= 18 else f"{label[:15]}..."
            x_center = rect.left() + (slot_width * index) + (slot_width / 2)
            bar_left = x_center - (bar_width / 2)
            bar_height = 0 if max_value <= 0 else (revenue / max_value) * rect.height()
            bar_top = rect.bottom() - bar_height
            color = self.palette_colors[index % len(self.palette_colors)]

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(bar_left, bar_top, bar_width, max(8, bar_height)), 8, 8)

            painter.setPen(QColor("#4a3123"))
            painter.drawText(QRectF(bar_left - 10, bar_top - 24, bar_width + 20, 18), Qt.AlignCenter, f"\u20b1{revenue}")
            painter.setPen(QColor("#725f51"))
            painter.drawText(QRectF(bar_left - 18, rect.bottom() + 8, bar_width + 36, 34), Qt.AlignHCenter | Qt.TextWordWrap, short_label)

        painter.setPen(QColor("#9e816b"))
        for step in steps:
            y = rect.bottom() - (step / max_value) * rect.height()
            painter.drawText(10, int(y + 5), f"\u20b1{step}")


class ToastNotification(QFrame):
    def __init__(self, parent, title, message, kind="info", duration_ms=2600):
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        palette = {
            "success": ("#f1fbf3", "#d5eddc", "#2d6a3d", "✓"),
            "error": ("#fff4f2", "#f1d2ca", "#9f3f30", "!"),
            "warning": ("#fff8ef", "#efd9b8", "#9a6431", "!"),
            "info": ("#f6f7fb", "#d9dfee", "#455a87", "i"),
        }
        bg, border, accent, badge_text = palette.get(kind, palette["info"])

        self.setStyleSheet(f"""
            QFrame#toastNotification {{
                background:{bg};
                border:1px solid {border};
                border-radius:18px;
            }}
            QLabel {{
                background:transparent;
                border:none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(12)

        badge = QLabel(badge_text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(34, 34)
        badge.setStyleSheet(f"""
            background:{accent};
            color:white;
            border-radius:17px;
            font-size:17px;
            font-weight:900;
        """)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:14px; font-weight:900; color:#2a1a12;")
        message_lbl = QLabel(message)
        message_lbl.setWordWrap(True)
        message_lbl.setStyleSheet("font-size:13px; color:#6e5f56;")

        text_col.addWidget(title_lbl)
        text_col.addWidget(message_lbl)

        close_btn = QPushButton("×")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{accent};
                border:none;
                font-size:18px;
                font-weight:900;
            }}
        """)
        close_btn.clicked.connect(self.close)

        layout.addWidget(badge, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        layout.addWidget(close_btn, 0, Qt.AlignTop)

        self.setMinimumWidth(380)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(duration_ms)

    def closeEvent(self, event):
        parent = self.parent()
        if parent and hasattr(parent, "remove_notification"):
            parent.remove_notification(self)
        super().closeEvent(event)


class NotificationCenterPopup(QDialog):
    def __init__(self, parent=None, notifications=None):
        super().__init__(parent)
        self.notifications = notifications or []
        dark_mode = dialog_prefers_dark(parent)

        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setModal(False)
        self.resize(420, 460)

        dialog_bg = "#241d18" if dark_mode else "#f7eadc"
        dialog_bg_alt = "#2d241e" if dark_mode else "#f2dfca"
        border_color = "#534136" if dark_mode else "#dfc1a7"
        card_bg = "#2f2620" if dark_mode else "#f9efe4"
        card_bg_alt = "#372d26" if dark_mode else "#f5e7d8"
        title_color = "#f0e3d4" if dark_mode else "#2a1a12"
        muted_text = "#c9b8aa" if dark_mode else "#7f6d62"

        self.setStyleSheet(f"""
            QDialog {{
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {dialog_bg}, stop:1 {dialog_bg_alt});
                border:1px solid {border_color};
                border-radius:24px;
            }}
            QLabel {{
                background:transparent;
                border:none;
            }}
            QFrame#notifCard {{
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {card_bg}, stop:1 {card_bg_alt});
                border:1px solid {border_color};
                border-radius:18px;
            }}
            QPushButton#notifAction {{
                background:#f1dcc6;
                color:#7b4b2f;
                border:1px solid #ddb996;
                border-radius:12px;
                padding:10px 14px;
                font-size:13px;
                font-weight:800;
            }}
            QPushButton#notifAction:hover {{
                background:#e8ceb3;
                color:#643a23;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon = QLabel("🔔")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(42, 42)
        icon.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff0df, stop:1 #f5dcc1);
            color:#9a5f37;
            border:1px solid #ead4bf;
            border-radius:14px;
            font-size:18px;
            font-weight:900;
        """)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel("System Notifications")
        title.setStyleSheet(f"font-size:20px; font-weight:900; color:{title_color};")
        subtitle = QLabel("Actionable updates for stock, shop hours, and products")
        subtitle.setStyleSheet(f"font-size:12px; color:{muted_text};")
        text_col.addWidget(title)
        text_col.addWidget(subtitle)

        header.addWidget(icon)
        header.addLayout(text_col, 1)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent;")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        if not self.notifications:
            empty = QFrame()
            empty.setObjectName("notifCard")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(18, 18, 18, 18)
            empty_layout.setSpacing(6)
            empty_title = QLabel("No notifications right now")
            empty_title.setStyleSheet(f"font-size:16px; font-weight:900; color:{title_color};")
            empty_text = QLabel("The system is running normally.")
            empty_text.setStyleSheet(f"font-size:12px; color:{muted_text};")
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_text)
            content_layout.addWidget(empty)
        else:
            for notification in self.notifications:
                card = QFrame()
                card.setObjectName("notifCard")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(16, 16, 16, 16)
                card_layout.setSpacing(8)

                top = QHBoxLayout()
                top.setContentsMargins(0, 0, 0, 0)
                top.setSpacing(10)

                kind_colors = {
                    "error": ("#fff0ec", "#c8513e"),
                    "warning": ("#fff7eb", "#af722f"),
                    "success": ("#eef9ef", "#4d8554"),
                    "info": ("#f3f6ff", "#5c72a8"),
                }
                bg, fg = kind_colors.get(notification.get("kind", "info"), kind_colors["info"])

                badge = QLabel(notification.get("icon", "!"))
                badge.setAlignment(Qt.AlignCenter)
                badge.setFixedSize(34, 34)
                badge.setStyleSheet(
                    f"background:{bg}; color:{fg}; border-radius:12px; font-size:15px; font-weight:900;"
                )

                title_wrap = QVBoxLayout()
                title_wrap.setSpacing(2)
                card_title = QLabel(notification.get("title", "Notification"))
                card_title.setStyleSheet(f"font-size:15px; font-weight:900; color:{title_color};")
                card_text = QLabel(notification.get("message", ""))
                card_text.setWordWrap(True)
                card_text.setStyleSheet(f"font-size:12px; color:{muted_text};")
                title_wrap.addWidget(card_title)
                title_wrap.addWidget(card_text)

                top.addWidget(badge, 0, Qt.AlignTop)
                top.addLayout(title_wrap, 1)
                card_layout.addLayout(top)

                action_label = notification.get("action_label")
                action_handler = notification.get("action")
                if action_label and action_handler:
                    action_btn = QPushButton(action_label)
                    action_btn.setObjectName("notifAction")
                    action_btn.clicked.connect(lambda checked=False, fn=action_handler: self.handle_action(fn))
                    card_layout.addWidget(action_btn, 0, Qt.AlignLeft)

                content_layout.addWidget(card)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def handle_action(self, handler):
        self.close()
        if callable(handler):
            handler()


def dialog_prefers_dark(parent):
    return bool(parent and hasattr(parent, "system_prefers_dark") and parent.system_prefers_dark())


class ConfirmActionDialog(QDialog):
    def __init__(self, parent=None, title="Confirm", message="Are you sure?", confirm_text="Yes", cancel_text="No"):
        super().__init__(parent)
        dark_mode = dialog_prefers_dark(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(360, 170)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        dialog_bg = "#241d18" if dark_mode else "rgba(255, 250, 244, 0.99)"
        border = "#534136" if dark_mode else "#e5d3c1"
        title_color = "#f4e6d8" if dark_mode else "#24160f"
        text_color = "#e7d6c6" if dark_mode else "#5a3c29"
        accent_bg = "#6f4430" if dark_mode else "#8d5a3c"
        secondary_bg = "#322821" if dark_mode else "#fff7ef"
        secondary_text = "#f0dfcf" if dark_mode else "#6b4731"

        self.setStyleSheet(f"""
            QDialog {{
                background:{dialog_bg};
                border:1px solid {border};
                border-radius:22px;
            }}
            QLabel {{
                background:transparent;
                border:none;
            }}
            QLabel#confirmTitle {{
                color:{title_color};
                font-size:16px;
                font-weight:900;
            }}
            QLabel#confirmMessage {{
                color:{text_color};
                font-size:15px;
                font-weight:700;
            }}
            QLabel#confirmIcon {{
                background:{accent_bg};
                color:white;
                border:none;
                border-radius:24px;
                min-width:48px;
                max-width:48px;
                min-height:48px;
                max-height:48px;
                font-size:26px;
                font-weight:500;
            }}
            QPushButton#primary {{
                background:{accent_bg};
                color:white;
                border:none;
                border-radius:12px;
                padding:10px 18px;
                font-size:14px;
                font-weight:800;
            }}
            QPushButton#primary:hover {{ background:#6d4027; }}
            QPushButton#secondary {{
                background:{secondary_bg};
                color:{secondary_text};
                border:1px solid {border};
                border-radius:12px;
                padding:10px 18px;
                font-size:14px;
                font-weight:800;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(16)

        header = QLabel(title)
        header.setObjectName("confirmTitle")
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        icon = QLabel("?")
        icon.setObjectName("confirmIcon")
        icon.setAlignment(Qt.AlignCenter)
        msg = QLabel(message)
        msg.setObjectName("confirmMessage")
        msg.setWordWrap(True)
        body.addWidget(icon, 0, Qt.AlignTop)
        body.addWidget(msg, 1)
        root.addLayout(body)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setObjectName("primary")
        confirm_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(confirm_btn)
        root.addLayout(actions)


class AddEditProductDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product or {}
        self.image_path = self.product.get("image", "")
        self.image_display_path = self.image_path
        dark_mode = dialog_prefers_dark(parent)

        self.setWindowTitle("Product")
        self.setModal(True)
        self.resize(700, 610)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        dialog_bg = "#241d18" if dark_mode else "rgba(255, 250, 244, 0.98)"
        text_color = "#f0e3d4" if dark_mode else "#1f160f"
        field_bg = "#2f2620" if dark_mode else "rgba(255, 255, 255, 0.78)"
        field_border = "#534136" if dark_mode else "#e5d3c1"
        secondary_bg = "#322821" if dark_mode else "rgba(255,255,255,0.4)"
        secondary_hover = "#3a2f27" if dark_mode else "rgba(255,255,255,0.65)"
        secondary_text = "#f0dfcf" if dark_mode else "#5c3a27"
        preview_bg = "#2a221d" if dark_mode else "rgba(255,255,255,0.35)"
        preview_border = "#4d3d32" if dark_mode else "#e9d8c7"

        self.setStyleSheet(f"""
            QDialog {{
                background:{dialog_bg};
                border:1px solid {field_border};
                border-radius:22px;
            }}
            QLabel {{
                background:transparent;
                color:{text_color};
                border:none;
                padding:0;
                margin:0;
            }}
            QLineEdit, QTextEdit {{
                background:{field_bg};
                color:{text_color};
                border:1px solid {field_border};
                border-radius:14px;
                padding:12px 14px;
                font-size:14px;
            }}
            QPushButton#primary {{
                background:#6f4430;
                color:white;
                border:none;
                border-radius:14px;
                padding:14px 18px;
                font-size:15px;
                font-weight:800;
            }}
            QPushButton#primary:hover {{ background:#5b3525; }}
            QPushButton#secondary {{
                background:{secondary_bg};
                color:{secondary_text};
                border:1px solid {field_border};
                border-radius:12px;
                padding:12px 16px;
                font-size:14px;
                font-weight:700;
            }}
            QPushButton#secondary:hover {{ background:{secondary_hover}; }}
            QFrame#previewBox {{
                background:{preview_bg};
                border:1px solid {preview_border};
                border-radius:16px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Edit Product" if product else "Add New Product")
        title.setStyleSheet("font-size:24px; font-weight:900;")
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        self.name_input = QLineEdit()
        self.name_input.setText(self.product.get("name", ""))

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("e.g., Classic, Signature, Specialty")
        self.category_input.setText(self.product.get("category", ""))

        self.price_input = QLineEdit()
        self.price_input.setText(self.product.get("price_text", ""))

        self.available_input = QComboBox()
        self.available_input.addItems(["Available", "Not Available"])
        self.available_input.setCurrentText("Available" if self.product.get("available", True) else "Not Available")

        self.image_input = QLineEdit()
        self.image_input.setPlaceholderText("Selected image path...")
        self.image_input.setText(self.image_display_path)
        self.image_input.setReadOnly(True)

        root.addWidget(self.field("Product Name", self.name_input))
        root.addWidget(self.field("Category", self.category_input))
        root.addWidget(self.field("Price (₱)", self.price_input))

        root.addWidget(self.field("Availability", self.available_input))

        preview_wrap = QWidget()
        preview_lay = QVBoxLayout(preview_wrap)
        preview_lay.setContentsMargins(0, 0, 0, 0)
        preview_lay.setSpacing(8)

        img_lbl = QLabel("Product Image")
        img_lbl.setStyleSheet("font-size:15px; font-weight:700;")
        preview_lay.addWidget(img_lbl)

        self.preview_box = QFrame()
        self.preview_box.setObjectName("previewBox")
        box_lay = QVBoxLayout(self.preview_box)
        box_lay.setContentsMargins(14, 14, 14, 14)
        box_lay.setSpacing(12)

        self.preview_image = QLabel("No image selected")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setFixedHeight(170)
        self.preview_image.setStyleSheet("""
            background:transparent;
            border:none;
            border-radius:14px;
            color:#8b7b70;
            font-size:15px;
        """)

        pick_btn = QPushButton("Choose Image")
        pick_btn.setObjectName("secondary")
        pick_btn.clicked.connect(self.pick_image)

        box_lay.addWidget(self.preview_image)
        box_lay.addWidget(self.image_input)
        box_lay.addWidget(pick_btn)
        preview_lay.addWidget(self.preview_box)
        root.addWidget(preview_wrap)

        self.submit_btn = QPushButton("Update Product" if product else "Add Product")
        self.submit_btn.setObjectName("primary")
        self.submit_btn.clicked.connect(self.accept)
        root.addWidget(self.submit_btn)

        self.update_preview()

    def validate_form(self):
        name = self.name_input.text().strip()
        category = self.category_input.text().strip()
        price_text = self.price_input.text().strip()

        if not name:
            show_themed_message(self, "Missing Product Name", "Please enter a product name.", "warning")
            self.name_input.setFocus()
            return False

        if not category:
            show_themed_message(self, "Missing Category", "Please enter a category.", "warning")
            self.category_input.setFocus()
            return False

        if not price_text:
            show_themed_message(self, "Missing Price", "Please enter a price.", "warning")
            self.price_input.setFocus()
            return False

        parts = [part.strip() for part in price_text.split("/")]
        if len(parts) > 2 or any(not part for part in parts):
            show_themed_message(self, "Invalid Price", "Use a valid price like 99 or 99/120.", "warning")
            self.price_input.setFocus()
            self.price_input.selectAll()
            return False

        try:
            values = [float(part.replace(",", "")) for part in parts]
        except ValueError:
            show_themed_message(self, "Invalid Price", "Price must contain numbers only.", "warning")
            self.price_input.setFocus()
            self.price_input.selectAll()
            return False

        if any(value <= 0 for value in values):
            show_themed_message(self, "Invalid Price", "Price must be greater than 0.", "warning")
            self.price_input.setFocus()
            self.price_input.selectAll()
            return False

        return True

    def accept(self):
        if not self.validate_form():
            return
        super().accept()

    def field(self, label_text, widget):
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size:15px; font-weight:700;")
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return wrap

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Product Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.image_path = path
            self.image_display_path = path
            self.image_input.setText(path)
            self.update_preview()

    def update_preview(self):
        if self.image_path:
            pix = QPixmap(resolve_product_image_path(self.image_path))
            if pix and not pix.isNull():
                self.preview_image.setPixmap(
                    pix.scaled(300, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self.preview_image.setText("")
                return
        self.preview_image.setPixmap(QPixmap())
        self.preview_image.setText("No image selected")

    def set_submit_state(self, busy):
        if not hasattr(self, "submit_btn"):
            return
        self.submit_btn.setEnabled(not busy)
        self.submit_btn.setText("Saving Product..." if busy else ("Update Product" if self.product else "Add Product"))
        QApplication.processEvents()


class RestockDialog(QDialog):
    def __init__(self, parent=None, item_name="Black Tea Leaves", current_stock="15 kg"):
        super().__init__(parent)
        self.item_name = item_name
        self.base_value = int(str(current_stock).split()[0])
        self.unit = "kg" if "kg" in current_stock else "pieces"
        dark_mode = dialog_prefers_dark(parent)

        self.setWindowTitle("Restock")
        self.setModal(True)
        self.resize(620, 420)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        dialog_bg = "#241d18" if dark_mode else "#fffaf5"
        text_color = "#f0e3d4" if dark_mode else "#1f160f"
        field_bg = "#2f2620" if dark_mode else "rgba(255, 250, 244, 0.96)"
        border_color = "#534136" if dark_mode else "#dec6b2"
        card_bg = "#2c231d" if dark_mode else "rgba(255, 251, 247, 0.9)"
        preview_bg = "#322821" if dark_mode else "rgba(247, 237, 227, 0.92)"

        self.setStyleSheet(f"""
            QDialog {{
                background:{dialog_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QLabel {{
                background:transparent;
                color:{text_color};
                border:none;
                padding:0;
                margin:0;
            }}
            QSpinBox {{
                background:{field_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:14px;
                padding:10px 14px;
                font-size:16px;
            }}
            QPushButton#primary {{
                background:#8b5638;
                color:white;
                border:none;
                border-radius:14px;
                padding:14px 18px;
                font-size:15px;
                font-weight:800;
            }}
            QPushButton#primary:disabled {{
                background:#8e8e98;
            }}
            QPushButton#primary:hover {{
                background:#75462d;
            }}
            QFrame#preview {{
                background:{preview_bg};
                border:1px solid {border_color};
                border-radius:18px;
            }}
            QFrame#stockCard {{
                background:{card_bg};
                border:1px solid {border_color};
                border-radius:20px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel(f"Restock {item_name}")
        title.setStyleSheet("font-size:22px; font-weight:900;")
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        stock_card = QFrame()
        stock_card.setObjectName("stockCard")
        stock_layout = QVBoxLayout(stock_card)
        stock_layout.setContentsMargins(16, 14, 16, 14)
        stock_layout.setSpacing(6)
        current_label = QLabel("Current Stock")
        current_label.setStyleSheet("font-size:13px; font-weight:700; color:#7c675b;")
        current_value = QLabel(f"{self.base_value} {self.unit}")
        current_value.setStyleSheet("font-size:28px; font-weight:900; color:#2a1a12;")
        stock_layout.addWidget(current_label)
        stock_layout.addWidget(current_value)
        root.addWidget(stock_card)

        qty_label = QLabel("Quantity to Add")
        qty_label.setStyleSheet("font-size:14px; font-weight:700;")
        self.qty = QSpinBox()
        self.qty.setRange(0, 9999)
        self.qty.setValue(0)
        self.qty.valueChanged.connect(self.update_preview)
        self.qty.setFixedHeight(48)
        root.addWidget(qty_label)
        root.addWidget(self.qty)

        preview = QFrame()
        preview.setObjectName("preview")
        preview_lay = QVBoxLayout(preview)
        preview_lay.setContentsMargins(18, 14, 18, 14)
        self.preview_text = QLabel("")
        self.preview_text.setStyleSheet("font-size:16px; color:#8b5638; font-weight:800;")
        preview_lay.addWidget(self.preview_text)
        root.addWidget(preview)

        self.confirm_btn = QPushButton("Confirm Restock")
        self.confirm_btn.setObjectName("primary")
        self.confirm_btn.clicked.connect(self.confirm_restock)
        root.addWidget(self.confirm_btn)

        self.update_preview()

    def update_preview(self):
        new_total = self.base_value + self.qty.value()
        self.preview_text.setText(f"New Stock Level: <b>{new_total} {self.unit}</b>")
        self.confirm_btn.setEnabled(self.qty.value() > 0)

    def confirm_restock(self):
        if self.parent() and hasattr(self.parent(), "show_notification"):
            self.parent().show_notification("Restock", f"{self.item_name} restocked successfully.", "success")
        self.accept()

    def set_submit_state(self, busy):
        self.confirm_btn.setEnabled(not busy)
        self.confirm_btn.setText("Restocking..." if busy else "Confirm Restock")
        QApplication.processEvents()


class AddInventoryItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        dark_mode = dialog_prefers_dark(parent)
        self.setWindowTitle("New Inventory Item")
        self.setModal(True)
        self.resize(520, 420)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        dialog_bg = "#241d18" if dark_mode else "#fffaf5"
        text_color = "#f0e3d4" if dark_mode else "#1f160f"
        field_bg = "#2f2620" if dark_mode else "rgba(255, 250, 244, 0.96)"
        border_color = "#534136" if dark_mode else "#dec6b2"
        secondary_bg = "#322821" if dark_mode else "rgba(255, 251, 247, 0.95)"
        secondary_text = "#f0dfcf" if dark_mode else "#7b4d32"

        self.setStyleSheet(f"""
            QDialog {{
                background:{dialog_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QFrame#dialogShell {{
                background:{dialog_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QLabel {{
                background:transparent;
                color:{text_color};
                border:none;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background:{field_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:14px;
                padding:10px 14px;
                font-size:14px;
                min-height:22px;
            }}
            QPushButton#primary {{
                background:#8b5638;
                color:white;
                border:none;
                border-radius:14px;
                padding:12px 18px;
                font-size:15px;
                font-weight:800;
            }}
            QPushButton#primary:hover {{ background:#75462d; }}
            QPushButton#secondary {{
                background:{secondary_bg};
                color:{secondary_text};
                border:1px solid {border_color};
                border-radius:14px;
                padding:12px 18px;
                font-size:14px;
                font-weight:700;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("Add New Inventory Item")
        title.setStyleSheet("font-size:22px; font-weight:900; color:#241610;")
        root.addWidget(title)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Item name")

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("Category")

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["kg", "liters", "pieces", "packs"])

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 999999)

        self.reorder_input = QSpinBox()
        self.reorder_input.setRange(0, 999999)

        for label_text, widget in [
            ("Item Name", self.name_input),
            ("Category", self.category_input),
            ("Unit", self.unit_combo),
            ("Current Stock", self.quantity_input),
            ("Reorder Level", self.reorder_input),
        ]:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size:14px; font-weight:800;")
            lay.addWidget(lbl)
            lay.addWidget(widget)
            root.addWidget(wrap)

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Item")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        root.addLayout(actions)


class UserEditDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = dict(user or {})
        self.setWindowTitle("Edit User")
        self.setModal(True)
        self.resize(460, 360)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QDialog {
                background:#fff9f4;
                border:1px solid #dfc2ab;
                border-radius:24px;
            }
            QLabel {
                background:transparent;
                color:#241610;
                border:none;
            }
            QLineEdit, QComboBox {
                background:#fffdf9;
                color:#2b1b14;
                border:1px solid #dfc2ab;
                border-radius:16px;
                padding:14px 16px;
                font-size:18px;
                font-weight:800;
                min-height:28px;
            }
            QCheckBox {
                background:transparent;
                color:#6f5646;
                font-size:16px;
                font-weight:900;
                spacing:10px;
            }
            QCheckBox::indicator {
                width:18px;
                height:18px;
                border-radius:6px;
            }
            QPushButton#primary {
                background:#9a613d;
                color:white;
                border:none;
                border-radius:16px;
                padding:14px 18px;
                font-size:17px;
                font-weight:900;
            }
            QPushButton#primary:hover { background:#7f4e31; }
            QPushButton#secondary {
                background:#fffdf9;
                color:#7b4d32;
                border:1px solid #dfc2ab;
                border-radius:16px;
                padding:14px 18px;
                font-size:17px;
                font-weight:900;
            }
            QPushButton#titleClose {
                background:transparent;
                color:#7b4d32;
                border:none;
                border-radius:14px;
                font-size:24px;
                font-weight:900;
                min-width:36px;
                max-width:36px;
                min-height:36px;
                max-height:36px;
            }
            QPushButton#titleClose:hover {
                background:#f4e1d2;
                color:#5f3823;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(14)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(2, 0, 2, 0)
        title_bar.setSpacing(10)

        badge = QLabel("U")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(34, 34)
        badge.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f6e7d9, stop:1 #f2d8c4);
            color:#8b5638;
            border:1px solid #dfc2ab;
            border-radius:17px;
            font-size:16px;
            font-weight:900;
        """)
        title_bar.addWidget(badge)

        title_text = QLabel("Edit User")
        title_text.setStyleSheet("font-size:18px; font-weight:900; color:#3a2418;")
        title_bar.addWidget(title_text)
        title_bar.addStretch()

        close_btn = QPushButton("×")
        close_btn.setObjectName("titleClose")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        title_bar.addWidget(close_btn)
        root.addLayout(title_bar)

        line = QFrame()
        line.setStyleSheet("background:#ead7c7; min-height:1px; max-height:1px; border:none;")
        root.addWidget(line)

        title = QLabel(f"Edit {self.user.get('username', 'User')}")
        title.setStyleSheet("font-size:26px; font-weight:900; color:#241610;")
        root.addWidget(title)

        username_lbl = QLabel(f"Username: {self.user.get('username', '-')}")
        username_lbl.setStyleSheet("font-size:16px; font-weight:700; color:#8c796d;")
        root.addWidget(username_lbl)

        self.full_name_input = QLineEdit()
        self.full_name_input.setText(str(self.user.get("full_name", "")))

        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "cashier", "customer"])
        role_value = str(self.user.get("role", "admin")).strip().lower() or "admin"
        role_index = max(0, self.role_combo.findText(role_value))
        self.role_combo.setCurrentIndex(role_index)

        self.active_check = QCheckBox("Active account")
        self.active_check.setChecked(int(self.user.get("is_active", 1) or 0) == 1)

        for label_text, widget in [
            ("Full Name", self.full_name_input),
            ("Role", self.role_combo),
        ]:
            wrap = QWidget()
            lay = QVBoxLayout(wrap)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size:17px; font-weight:900; color:#3d2619;")
            lay.addWidget(lbl)
            lay.addWidget(widget)
            root.addWidget(wrap)

        root.addWidget(self.active_check)
        root.addStretch()

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        root.addLayout(actions)

    def form_data(self):
        return {
            "full_name": self.full_name_input.text().strip(),
            "role": self.role_combo.currentText().strip().lower(),
            "is_active": self.active_check.isChecked(),
        }


class OrderCustomizeDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product or {}
        self.parent_dashboard = parent
        self.small_price, self.large_price = self.resolve_size_prices()
        self.addon_checks = []
        dark_mode = dialog_prefers_dark(parent)

        self.setWindowTitle("Customize Order")
        self.setModal(True)
        self.resize(520, 700)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        dialog_bg = "#241d18" if dark_mode else "#fff7ef"
        text_color = "#f0e3d4" if dark_mode else "#1f160f"
        card_bg = "#2d241e" if dark_mode else "#fff8f1"
        section_bg = "#2f2620" if dark_mode else "rgba(255, 248, 240, 0.92)"
        total_bg = "#2d241e" if dark_mode else "#fff8f1"
        border_color = "#534136" if dark_mode else "#dfc2ab"
        secondary_bg = "#322821" if dark_mode else "rgba(255, 251, 247, 0.95)"
        secondary_text = "#f0dfcf" if dark_mode else "#7b4d32"
        muted_text = "#c7b7aa" if dark_mode else "#2c1c13"
        combo_style = f"""
            background:{section_bg};
            color:{text_color};
            border:1px solid {border_color};
            border-radius:14px;
            padding:10px 14px;
            font-size:14px;
        """
        line_edit_style = f"""
            background:{section_bg};
            color:{text_color};
            border:1px solid {border_color};
            border-radius:14px;
            padding:10px 14px;
            font-size:14px;
        """
        hero_style = f"QFrame#heroCard {{ background:{card_bg}; border:1px solid {border_color}; border-radius:22px; }}"
        section_card_style = f"QFrame#sectionCard {{ background:{section_bg}; border:1px solid {border_color}; border-radius:20px; }}"
        total_card_style = f"QFrame#totalCard {{ background:{total_bg}; border:1px solid {border_color}; border-radius:22px; }}"
        primary_btn_style = """
            QPushButton {
                background:#8b5638;
                color:white;
                border:none;
                border-radius:16px;
                padding:12px 18px;
                font-size:15px;
                font-weight:800;
            }
            QPushButton:hover { background:#74442b; }
        """
        secondary_btn_style = f"""
            QPushButton {{
                background:{secondary_bg};
                color:{secondary_text};
                border:1px solid {border_color};
                border-radius:16px;
                padding:12px 18px;
                font-size:14px;
                font-weight:700;
            }}
            QPushButton:hover {{ background:{'#3a2f27' if dark_mode else '#f7eee6'}; }}
        """
        stepper_style = f"""
            QPushButton {{
                background:{section_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:16px;
                font-size:20px;
                font-weight:900;
                min-width:48px;
                max-width:48px;
                min-height:48px;
                max-height:48px;
            }}
            QPushButton:hover {{ background:{'#3a2f27' if dark_mode else '#f7eee6'}; }}
        """

        self.setStyleSheet(f"""
            QDialog {{
                background:{dialog_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QFrame#dialogShell {{
                background:{dialog_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QLabel {{
                background:transparent;
                color:{text_color};
                border:none;
            }}
            QFrame#heroCard {{
                background:{card_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QFrame#sectionCard {{
                background:{section_bg};
                border:1px solid {border_color};
                border-radius:20px;
            }}
            QFrame#totalCard {{
                background:{total_bg};
                border:1px solid {border_color};
                border-radius:22px;
            }}
            QComboBox {{
                background:{section_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:14px;
                padding:10px 14px;
                font-size:14px;
            }}
            QLineEdit {{
                background:{section_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:14px;
                padding:10px 14px;
                font-size:14px;
            }}
            QLineEdit::placeholder {{
                color:{'#bdaea3' if dark_mode else '#8f7665'};
            }}
            QCheckBox {{
                background:transparent;
                spacing:10px;
                font-size:14px;
                color:{muted_text};
                padding:3px 0;
            }}
            QCheckBox::indicator {{
                width:18px;
                height:18px;
                border:1px solid {border_color};
                border-radius:6px;
                background:{section_bg};
            }}
            QCheckBox::indicator:checked {{
                background:#a86339;
                border:1px solid #a86339;
            }}
            QScrollArea {{
                background:transparent;
                border:none;
            }}
            QScrollBar:vertical {{
                background:transparent;
                width:10px;
                margin:10px 2px 10px 0;
            }}
            QScrollBar::handle:vertical {{
                background:#d4b79f;
                border-radius:5px;
                min-height:42px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height:0px;
                background:transparent;
                border:none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background:transparent;
            }}
            QPushButton#primary {{
                background:#8b5638;
                color:white;
                border:none;
                border-radius:16px;
                padding:12px 18px;
                font-size:15px;
                font-weight:800;
            }}
            QPushButton#primary:hover {{ background:#74442b; }}
            QPushButton#secondary {{
                background:{secondary_bg};
                color:{secondary_text};
                border:1px solid {border_color};
                border-radius:16px;
                padding:12px 18px;
                font-size:14px;
                font-weight:700;
            }}
            QPushButton#secondary:hover {{ background:#3a2f27; }}
            QPushButton#stepper {{
                background:{section_bg};
                color:{text_color};
                border:1px solid {border_color};
                border-radius:16px;
                font-size:20px;
                font-weight:900;
                min-width:48px;
                max-width:48px;
                min-height:48px;
                max-height:48px;
            }}
            QPushButton#stepper:hover {{ background:#3a2f27; }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")
        scroll.viewport().setStyleSheet("background:transparent; border:none;")

        shell = QFrame()
        shell.setObjectName("dialogShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        shell.setStyleSheet(f"QFrame#dialogShell {{ background:{dialog_bg}; border:1px solid {border_color}; border-radius:22px; }}")

        root = QVBoxLayout(shell)
        root.setContentsMargins(16, 18, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("Add Order")
        title.setStyleSheet("font-size:22px; font-weight:900; color:#241610;")
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero.setAttribute(Qt.WA_StyledBackground, True)
        hero.setStyleSheet(hero_style)
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(14, 14, 14, 14)
        hero_lay.setSpacing(12)

        image_lbl = QLabel()
        image_lbl.setFixedSize(96, 96)
        image_lbl.setAlignment(Qt.AlignCenter)
        image_lbl.setStyleSheet("border-radius:18px; background:#e8f1d7; border:1px solid #ddc4ae;")

        if parent and hasattr(parent, "render_product_image"):
            rendered = parent.render_product_image(
                self.product.get("image", ""),
                QSize(96, 96),
                parent.product_image_background(self.product.get("category", ""))
            )
            if rendered:
                image_lbl.setPixmap(rendered)
        if image_lbl.pixmap() is None:
            image_lbl.setText("Drink")
            image_lbl.setStyleSheet("border-radius:18px; background:#e8f1d7; border:1px solid #ddc4ae; color:#6f6657; font-weight:700;")

        hero_text = QVBoxLayout()
        hero_text.setSpacing(6)

        name_lbl = QLabel(str(self.product.get("name", "Product")))
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet("font-size:19px; font-weight:900; color:#1f160f;")

        desc_lbl = QLabel(str(self.product.get("desc", "")))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size:13px; color:#7e6f66;")

        price_lbl = QLabel(self.current_unit_price_text())
        price_lbl.setStyleSheet("font-size:17px; font-weight:900; color:#bc5d28;")
        self.price_lbl = price_lbl

        hero_text.addWidget(name_lbl)
        hero_text.addWidget(desc_lbl)
        hero_text.addWidget(price_lbl)
        hero_text.addStretch()

        hero_lay.addWidget(image_lbl)
        hero_lay.addLayout(hero_text, 1)
        root.addWidget(hero)

        root.addWidget(self.section_label("Cup Size"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Solo", "Large"])
        self.size_combo.currentIndexChanged.connect(self.update_total)
        self.size_combo.setStyleSheet(combo_style)
        root.addWidget(self.size_combo)

        root.addWidget(self.section_label("Customer Name"))
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("Enter customer name")
        self.customer_name_input.setText("Walk-in Customer")
        self.customer_name_input.setStyleSheet(line_edit_style)
        root.addWidget(self.customer_name_input)

        root.addWidget(self.section_label("Order Type"))
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["Dine-in", "Takeout"])
        self.order_type_combo.setStyleSheet(combo_style)
        root.addWidget(self.order_type_combo)

        root.addWidget(self.section_label("Add-ons"))
        addons_card = QFrame()
        addons_card.setObjectName("sectionCard")
        addons_card.setAttribute(Qt.WA_StyledBackground, True)
        addons_card.setStyleSheet(section_card_style)
        addons_lay = QVBoxLayout(addons_card)
        addons_lay.setContentsMargins(14, 12, 14, 12)
        addons_lay.setSpacing(6)
        addons_card.setMaximumHeight(138)
        for addon in self.available_addons():
            addon_name = str(addon.get("name", "Add-on")).strip() or "Add-on"
            addon_price = self.safe_int(addon.get("price", 0))
            check = QCheckBox(f"{addon_name} (+Php {addon_price})")
            check.setProperty("addon_name", addon_name)
            check.setProperty("addon_price", addon_price)
            check.setStyleSheet("background:transparent;")
            check.toggled.connect(self.update_total)
            self.addon_checks.append(check)
            addons_lay.addWidget(check)
        if not self.addon_checks:
            no_addon = QLabel("No add-ons available in the system.")
            no_addon.setStyleSheet("font-size:13px; color:#8a776b;")
            addons_lay.addWidget(no_addon)
        root.addWidget(addons_card)

        root.addWidget(self.section_label("Quantity"))
        quantity_card = QFrame()
        quantity_card.setObjectName("sectionCard")
        quantity_card.setAttribute(Qt.WA_StyledBackground, True)
        quantity_card.setStyleSheet(section_card_style)
        quantity_lay = QHBoxLayout(quantity_card)
        quantity_lay.setContentsMargins(14, 12, 14, 12)
        quantity_lay.setSpacing(14)

        minus_btn = QPushButton("-")
        minus_btn.setObjectName("stepper")
        minus_btn.setStyleSheet(stepper_style)
        minus_btn.clicked.connect(self.decrease_quantity)

        plus_btn = QPushButton("+")
        plus_btn.setObjectName("stepper")
        plus_btn.setStyleSheet(stepper_style)
        plus_btn.clicked.connect(self.increase_quantity)

        self.quantity_label = QLabel("1")
        self.quantity_label.setAlignment(Qt.AlignCenter)
        self.quantity_label.setStyleSheet("font-size:26px; font-weight:900; color:#1f160f; min-width:60px;")

        quantity_lay.addWidget(minus_btn)
        quantity_lay.addStretch()
        quantity_lay.addWidget(self.quantity_label)
        quantity_lay.addStretch()
        quantity_lay.addWidget(plus_btn)
        root.addWidget(quantity_card)

        total_card = QFrame()
        total_card.setObjectName("totalCard")
        total_card.setAttribute(Qt.WA_StyledBackground, True)
        total_card.setStyleSheet(total_card_style)
        total_lay = QHBoxLayout(total_card)
        total_lay.setContentsMargins(16, 14, 16, 14)

        total_text = QVBoxLayout()
        total_caption = QLabel("Total")
        total_caption.setStyleSheet("font-size:13px; font-weight:700; color:#8b776a;")
        self.total_value_lbl = QLabel()
        self.total_value_lbl.setStyleSheet("font-size:24px; font-weight:900; color:#bc5d28;")
        total_text.addWidget(total_caption)
        total_text.addWidget(self.total_value_lbl)

        total_lay.addLayout(total_text)
        total_lay.addStretch()
        root.addWidget(total_card)

        root.addWidget(self.section_label("Amount Tendered"))
        self.amount_tendered_input = QLineEdit()
        self.amount_tendered_input.setPlaceholderText("Enter cash amount")
        self.amount_tendered_input.textChanged.connect(self.update_total)
        self.amount_tendered_input.setStyleSheet(line_edit_style)
        root.addWidget(self.amount_tendered_input)

        change_card = QFrame()
        change_card.setObjectName("totalCard")
        change_card.setAttribute(Qt.WA_StyledBackground, True)
        change_card.setStyleSheet(total_card_style)
        change_lay = QHBoxLayout(change_card)
        change_lay.setContentsMargins(16, 14, 16, 14)

        change_text = QVBoxLayout()
        change_caption = QLabel("Change")
        change_caption.setStyleSheet("font-size:13px; font-weight:700; color:#8b776a;")
        self.change_value_lbl = QLabel()
        self.change_value_lbl.setStyleSheet("font-size:24px; font-weight:900; color:#bc5d28;")
        change_text.addWidget(change_caption)
        change_text.addWidget(self.change_value_lbl)

        change_lay.addLayout(change_text)
        change_lay.addStretch()
        root.addWidget(change_card)

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.setStyleSheet(secondary_btn_style)
        cancel_btn.clicked.connect(self.reject)

        add_btn = QPushButton("Add to Order")
        add_btn.setObjectName("primary")
        add_btn.setStyleSheet(primary_btn_style)
        add_btn.clicked.connect(self.confirm_order)
        self.add_btn = add_btn

        actions.addWidget(cancel_btn)
        actions.addWidget(add_btn)
        root.addLayout(actions)

        self.update_total()
        scroll.setWidget(shell)
        outer.addWidget(scroll)
        self.setStyleSheet(self.styleSheet())

    def section_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size:16px; font-weight:800; color:#2a1a12; margin-top:2px;")
        return label

    def quantity(self):
        return max(1, int(self.quantity_label.text()))

    def safe_int(self, value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def money_input_value(self):
        raw = str(self.amount_tendered_input.text() if hasattr(self, "amount_tendered_input") else "").strip()
        cleaned = raw.replace("\u20b1", "").replace("Php", "").replace("php", "").replace(",", "").strip()
        try:
            return int(float(cleaned))
        except (TypeError, ValueError):
            return 0

    def resolve_size_prices(self):
        if not self.parent_dashboard:
            return 0, 0

        raw = str(self.product.get("price_text", "0")).replace("\u20b1", "").replace(",", "").strip()
        if "/" in raw:
            solo_raw, large_raw = raw.split("/", 1)
            return self.safe_int(solo_raw), self.safe_int(large_raw)

        base = self.parent_dashboard.price_value_from_text(raw)
        return base, base

    def available_addons(self):
        if self.parent_dashboard and hasattr(self.parent_dashboard, "load_order_addons"):
            return self.parent_dashboard.load_order_addons()
        return []

    def selected_size(self):
        if not hasattr(self, "size_combo") or self.size_combo is None:
            return "Solo"
        return self.size_combo.currentText().strip() or "Solo"

    def current_unit_price(self):
        return self.large_price if self.selected_size().lower() == "large" else self.small_price

    def current_unit_price_text(self):
        return f"Php {self.current_unit_price():,}"

    def increase_quantity(self):
        self.quantity_label.setText(str(self.quantity() + 1))
        self.update_total()

    def decrease_quantity(self):
        self.quantity_label.setText(str(max(1, self.quantity() - 1)))
        self.update_total()

    def selected_addons(self):
        return [check.property("addon_name") for check in self.addon_checks if check.isChecked()]

    def selected_addons_total(self):
        return sum(self.safe_int(check.property("addon_price")) for check in self.addon_checks if check.isChecked())

    def total_price(self):
        return (self.current_unit_price() + self.selected_addons_total()) * self.quantity()

    def change_amount(self):
        return max(0, self.money_input_value() - self.total_price())

    def update_total(self):
        self.price_lbl.setText(self.current_unit_price_text())
        self.total_value_lbl.setText(f"Php {self.total_price():,}")
        self.change_value_lbl.setText(f"Php {self.change_amount():,}")

    def confirm_order(self):
        if self.money_input_value() < self.total_price():
            if self.parent_dashboard and hasattr(self.parent_dashboard, "show_notification"):
                self.parent_dashboard.show_notification(
                    "Insufficient Payment",
                    "Kulangan ang ibinayad para sa order na ito.",
                    "warning",
                    2800
                )
            self.amount_tendered_input.setFocus()
            self.amount_tendered_input.selectAll()
            return
        self.accept()

    def order_data(self):
        return {
            "size": self.size_combo.currentText(),
            "customer_name": self.customer_name_input.text().strip() or "Walk-in Customer",
            "order_type": self.order_type_combo.currentText().strip() or "Dine-in",
            "addons": self.selected_addons(),
            "unit_price": self.current_unit_price(),
            "quantity": self.quantity(),
            "total_price": self.total_price(),
            "amount_tendered": self.money_input_value(),
            "change_amount": self.change_amount(),
        }


class AdminDashboard(QMainWindow):
    def __init__(self, user=None, login_window=None, controller=None):
        super().__init__()
        self.user = user
        self.login_window = login_window
        self.controller = controller or DashboardController()
        self.nav_buttons = []
        self.user_name_labels = []
        self.user_avatar_labels = []
        self.clock_labels = []
        self.date_labels = []
        self.notification_buttons = []
        self.notification_badges = []
        self.active_notifications = []
        self.notification_popup = None
        self.notification_state_cache = set()
        self._live_monitor_tick = 0
        self._live_monitor_refresh_in_progress = False
        self._prepared_pixmap_cache = {}
        self._rendered_product_image_cache = {}
        self._cashier_receipts_cache = None
        self._dirty_page_builders = {}
        self._scheduled_page_refreshes = set()
        self._stack_builder_names = []
        self._loaded_stack_pages = set()
        self._product_refresh_timer = QTimer(self)
        self._product_refresh_timer.setSingleShot(True)
        self._product_refresh_timer.timeout.connect(self.refresh_products_ui)
        self.shop_schedule = self.load_shop_schedule_from_database()

        # Products are now loaded from MySQL instead of hardcoded sample data.
        self.products = self.load_products_from_database()

        self.order_rows = self.build_default_order_rows()
        self.daily_product_sales = {}
        self.daily_size_counts = {"solo": 0, "large": 0}
        self.order_summary_storage_path = os.path.join(PROJECT_ROOT, "order_summary_history.json")
        self.order_summary_state = self.load_order_summary_state()
        self.rollover_order_summary_if_needed()
        self.dashboard_products = [
            {"name": "Tapioca Pearls", "subtitle": "Add-on", "price": "\u20b1120", "sold": "4 sold", "stock": "8 kg left", "accent": "#5d402f", "reorder": "15 kg", "emoji": "●"},
            {"name": "Fresh Milk", "subtitle": "Dairy", "price": "\u20b1100", "sold": "2 sold", "stock": "5 liters left", "accent": "#dfd4a7", "reorder": "30 liters", "emoji": "◫"},
            {"name": "Taro Powder", "subtitle": "Flavoring", "price": "\u20b150", "sold": "1 sold", "stock": "3 kg left", "accent": "#9d67ad", "reorder": "10 kg", "emoji": "◆"},
        ]
        # Inventory items are now loaded from MySQL instead of hardcoded sample data.
        self.inventory_items = self.load_inventory_from_database()
        self.analytics_revenue_labels = ["Apr 12", "Apr 13", "Apr 14", "Apr 15", "Apr 16", "Apr 17", "Apr 18"]
        self.analytics_revenue_values = [120, 180, 150, 210, 170, 240, 270]
        self.analytics_status = [
            ("#76b255", "Completed", 1, "50%"),
            ("#f0aa2b", "Preparing", 0, "0%"),
            ("#a87543", "Ready", 1, "50%"),
        ]
        self.analytics_products = [
            {"name": "Classic Milk Tea", "units": 2, "revenue": 160, "status": "Low"},
            {"name": "Brown Sugar Pearl", "units": 1, "revenue": 110, "status": "Medium"},
            {"name": "Taro Milk Tea", "units": 0, "revenue": 0, "status": "Low"},
            {"name": "Matcha Latte", "units": 0, "revenue": 0, "status": "Low"},
            {"name": "Wintermelon Tea", "units": 0, "revenue": 0, "status": "Low"},
        ]
        self.recent_activities = [
            {"color": "#b78664", "icon": "P", "title": 'New product "Taro Powder" added', "timestamp": "April 24, 2026 10:30 AM", "activity_type": "product_added"},
            {"color": "#bc8353", "icon": "S", "title": 'Stock updated for "Fresh Milk"', "timestamp": "April 24, 2026 09:15 AM", "activity_type": "stock_updated"},
            {"color": "#e7b14d", "icon": "!", "title": 'Low stock alert for "Tapioca Pearls"', "timestamp": "April 24, 2026 08:45 AM", "activity_type": "low_stock"},
            {"color": "#95ad72", "icon": "O", "title": 'Order completed', "timestamp": "April 23, 2026 04:20 PM", "activity_type": "order_completed", "product_name": "Wintermelon Tea"},
        ]

        self.setWindowTitle(self.dashboard_window_title())
        self.setGeometry(80, 40, 1450, 900)
        self.setMinimumSize(1280, 820)

        self.apply_system_theme()
        self.build_ui()
        if portable_fixed_window_mode():
            self.show()
        else:
            self.showMaximized()
        QTimer.singleShot(0, self.start_datetime_updates)
        QTimer.singleShot(0, self.start_live_monitoring)

    def current_user_role(self):
        return str((self.user or {}).get("role", "admin")).strip().lower() or "admin"

    def is_cashier_role(self):
        return self.current_user_role() == "cashier"

    def role_display_name(self):
        return "Cashier" if self.is_cashier_role() else "Admin"

    def dashboard_window_title(self):
        return f"Best Brew {self.role_display_name()} Dashboard"

    def dashboard_portal_label(self):
        return f"{self.role_display_name()} Portal"

    def dashboard_welcome_subtitle(self):
        if self.is_cashier_role():
            return "Welcome back, Cashier! Here's what's happening at the counter today."
        return "Welcome back, Admin! Here's what's happening with your store today."

    def current_user_name(self):
        username = str((self.user or {}).get("username", "")).strip()
        if username:
            latest_user = database.get_user_by_username(username)
            if latest_user:
                self.user = latest_user
        full_name = str((self.user or {}).get("full_name", "")).strip()
        if full_name:
            return full_name
        return "Cashier" if self.is_cashier_role() else "Administrator"

    def current_user_id(self):
        username = str((self.user or {}).get("username", "")).strip()
        if username:
            latest_user = database.get_user_by_username(username)
            if latest_user:
                self.user = latest_user
        try:
            return int((self.user or {}).get("user_id") or 0)
        except (TypeError, ValueError):
            return 0

    def current_user_initials(self):
        parts = [part for part in self.current_user_name().split() if part]
        initials = "".join(part[0] for part in parts[:2]).upper()
        return initials or ("CJ" if self.is_cashier_role() else "AD")

    def refresh_user_identity_labels(self):
        current_name = self.current_user_name()
        current_initials = self.current_user_initials()

        active_name_labels = []
        for label in self.user_name_labels:
            try:
                label.setText(current_name)
                active_name_labels.append(label)
            except RuntimeError:
                continue
        self.user_name_labels = active_name_labels

        active_avatar_labels = []
        for label in self.user_avatar_labels:
            try:
                label.setPixmap(QPixmap())
                label.setText(current_initials)
                active_avatar_labels.append(label)
            except RuntimeError:
                continue
        self.user_avatar_labels = active_avatar_labels

    def navigation_pages(self):
        pages = [
            ("Dashboard", self.nav_icon("dashboard.svg"), self.page_dashboard_v2),
            ("Inventory", self.nav_icon("inventory.svg"), self.page_inventory),
            ("Orders", self.nav_icon("orders.svg"), self.page_orders),
            ("Products", self.nav_icon("products.svg"), self.page_products),
            ("Analytics", self.nav_icon("analytics.svg"), self.page_analytics),
            ("Users", self.nav_icon("dashboard.svg"), self.page_users),
        ]
        if self.is_cashier_role():
            return [
                ("Dashboard", self.nav_icon("dashboard.svg"), self.page_dashboard_v2),
                ("Products", self.nav_icon("products.svg"), self.page_cashier_products),
                ("Receipts", self.nav_icon("analytics.svg"), self.page_cashier_receipts),
                ("Orders", self.nav_icon("inventory.svg"), self.page_cashier_orders),
            ]
        return pages

    def page_index_by_builder_name(self, builder_name):
        for index, (_, _, builder) in enumerate(self.navigation_pages()):
            if getattr(builder, "__name__", "") == builder_name:
                return index
        return None

    def switch_to_builder(self, builder_name, fallback_index=0):
        index = self.page_index_by_builder_name(builder_name)
        if index is None:
            index = fallback_index
        self.switch_page(index)

    def cashier_toolbar_button(self, text, primary=False, subtle=False, width=None):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        if width:
            btn.setFixedWidth(width)
        btn.setMinimumHeight(42)
        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9a5e34, stop:1 #7e4a29);
                    color:white;
                    border:none;
                    border-radius:12px;
                    padding:0 18px;
                    font-size:14px;
                    font-weight:800;
                }
                QPushButton:hover { background:#8a512d; }
            """)
        elif subtle:
            btn.setStyleSheet("""
                QPushButton {
                    background:#fffdfa;
                    color:#6b4a35;
                    border:1px solid #ead9c9;
                    border-radius:12px;
                    padding:0 16px;
                    font-size:13px;
                    font-weight:700;
                }
                QPushButton:hover { background:#fcf5ee; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background:#fff8f1;
                    color:#6b4a35;
                    border:1px solid #ead9c9;
                    border-radius:12px;
                    padding:0 16px;
                    font-size:13px;
                    font-weight:700;
                }
                QPushButton:hover { background:#fcf2e8; }
            """)
        return btn

    def cashier_receipt_action_button(self, text, width=70, icon_type=None):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(width, 36)
        dark_mode = self.system_prefers_dark()

        if icon_type == "view":
            background = "#352a22" if dark_mode else "#f6eadf"
            hover = "#43352b" if dark_mode else "#efdece"
            border = "#5d483a" if dark_mode else "#d8bba4"
            color = "#f1e4d6" if dark_mode else "#6e452b"
        elif icon_type == "print":
            background = "#2f261f" if dark_mode else "#efe2d4"
            hover = "#3b3028" if dark_mode else "#e7d4c1"
            border = "#584537" if dark_mode else "#d1b192"
            color = "#f0dfcf" if dark_mode else "#73482e"
        else:
            background = "#302720" if dark_mode else "#fff7ef"
            hover = "#3d3129" if dark_mode else "#f5e7d8"
            border = "#584537" if dark_mode else "#e2c9b4"
            color = "#f0dfcf" if dark_mode else "#7a5640"

        btn.setStyleSheet(f"""
            QPushButton {{
                background:{background};
                color:{color};
                border:1px solid {border};
                border-radius:10px;
                padding:0 14px;
                font-size:12px;
                font-weight:800;
            }}
            QPushButton:hover {{
                background:{hover};
                border:1px solid {border};
            }}
        """)
        return btn

    def cashier_receipt_payment_badge(self, payment_method):
        payment = str(payment_method or "Cash").strip() or "Cash"
        palette = {
            "cash": ("#e8f7ec", "#c8ead1", "#23924f", "■"),
            "gcash": ("#ebf3ff", "#cfe0ff", "#2c72db", "●"),
            "card": ("#f2ebff", "#dfd0ff", "#8a55da", "▲"),
        }
        bg, border, color, icon = palette.get(payment.lower(), ("#f7f0e8", "#ead9c9", "#8a654c", "•"))
        badge = QLabel(f"{icon} {payment}")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background:{bg};
            color:{color};
            border:1px solid {border};
            border-radius:10px;
            padding:4px 8px;
            font-size:11px;
            font-weight:800;
        """)
        return badge

    def cashier_search_field(self, placeholder, width=240):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedWidth(width)
        field.setMinimumHeight(42)
        field.setStyleSheet("""
            QLineEdit {
                background:#fffdfa;
                border:1px solid #ead9c9;
                border-radius:12px;
                padding:0 16px;
                font-size:13px;
                color:#3c291d;
            }
            QLineEdit::placeholder {
                color:#a28d7d;
            }
        """)
        return field

    def receipt_search_query(self):
        return str(getattr(self, "cashier_receipt_search_query", "") or "").strip()

    def set_receipt_search_query(self, value):
        self.cashier_receipt_search_query = str(value or "").strip()
        if hasattr(self, "cashier_receipts_table"):
            self.apply_cashier_receipt_table_filter()
        else:
            self.refresh_cashier_receipts_page()

    def filter_cashier_receipts(self, receipts):
        query = self.receipt_search_query().lower()
        return [receipt for receipt in receipts or [] if self.receipt_matches_query(receipt, query)]

    def receipt_matches_query(self, receipt, query=""):
        normalized_query = str(query or "").strip().lower()
        if not normalized_query:
            return True

        haystacks = [
            receipt.get("receipt_id", ""),
            receipt.get("order_id", ""),
            receipt.get("customer", ""),
            receipt.get("cashier", ""),
            receipt.get("payment", ""),
            receipt.get("order_type", ""),
            str(receipt.get("date_time", "")).replace("\n", " "),
        ]
        return any(normalized_query in str(value).lower() for value in haystacks)

    def replace_cashier_receipt_detail_card(self, receipt):
        detail_layout = getattr(self, "cashier_receipt_detail_layout", None)
        current_card = getattr(self, "cashier_receipt_detail_widget", None)
        if detail_layout is None:
            return
        if current_card is not None:
            detail_layout.removeWidget(current_card)
            current_card.deleteLater()
        next_card = self.cashier_receipt_detail_card(receipt)
        next_card.setMinimumWidth(330)
        next_card.setMaximumWidth(360)
        detail_layout.addWidget(next_card)
        self.cashier_receipt_detail_widget = next_card

    def refresh_cashier_receipt_row_highlight(self, featured_receipt_id):
        table = getattr(self, "cashier_receipts_table", None)
        receipts = getattr(self, "cashier_receipts_source", [])
        if table is None:
            return
        for row, receipt in enumerate(receipts):
            selected = receipt.get("receipt_id") == featured_receipt_id
            row_bg = QColor("#fdf4eb") if selected else QColor(Qt.transparent)
            for col in range(8):
                item = table.item(row, col)
                if item is not None:
                    item.setBackground(row_bg)

    def apply_cashier_receipt_table_filter(self):
        table = getattr(self, "cashier_receipts_table", None)
        receipts = getattr(self, "cashier_receipts_source", [])
        if table is None:
            return

        query = self.receipt_search_query()
        selected_receipt_id = str((getattr(self, "cashier_selected_receipt", {}) or {}).get("receipt_id", "")).strip()
        matched_receipts = []
        selected_match = None

        for row, receipt in enumerate(receipts):
            matched = self.receipt_matches_query(receipt, query)
            table.setRowHidden(row, not matched)
            if matched:
                matched_receipts.append(receipt)
                if receipt.get("receipt_id") == selected_receipt_id:
                    selected_match = receipt

        featured = selected_match or (matched_receipts[0] if matched_receipts else {
            "receipt_id": "-",
            "order_id": "-",
            "customer": "No matching receipt",
            "order_type": "-",
            "date_time": "-",
            "amount": "₱0.00",
            "payment": "-",
            "cashier": "-",
            "items": [],
            "subtotal": "₱0.00",
            "discount": "₱0.00",
            "tax": "₱0.00",
            "tendered": "₱0.00",
            "change": "₱0.00",
        })
        self.cashier_selected_receipt = dict(featured)
        self.refresh_cashier_receipt_row_highlight(featured.get("receipt_id"))
        self.replace_cashier_receipt_detail_card(featured)

    def cashier_demo_customers(self):
        return [
            {"id": "CUST-0001", "name": "Maria Santos", "phone": "0917 123 4567", "email": "maria.santos@email.com", "orders": 15, "spent": "₱2,450.00", "last_order": "May 4, 2026"},
            {"id": "CUST-0002", "name": "John Dela Cruz", "phone": "0918 987 6543", "email": "john.delacruz@email.com", "orders": 8, "spent": "₱1,320.00", "last_order": "May 3, 2026"},
            {"id": "CUST-0003", "name": "Ana Reyes", "phone": "0920 111 2222", "email": "ana.reyes@email.com", "orders": 12, "spent": "₱1,980.00", "last_order": "May 4, 2026"},
            {"id": "CUST-0004", "name": "Michael Tan", "phone": "0916 555 8888", "email": "michael.tan@email.com", "orders": 5, "spent": "₱850.00", "last_order": "May 2, 2026"},
            {"id": "CUST-0005", "name": "Liza Garcia", "phone": "0919 333 4444", "email": "liza.garcia@email.com", "orders": 7, "spent": "₱1,050.00", "last_order": "May 1, 2026"},
            {"id": "CUST-0006", "name": "Mark Lopez", "phone": "0930 222 1111", "email": "mark.lopez@email.com", "orders": 3, "spent": "₱460.00", "last_order": "Apr 30, 2026"},
            {"id": "CUST-0007", "name": "Samantha Cruz", "phone": "0915 777 8888", "email": "samantha.cruz@email.com", "orders": 9, "spent": "₱1,560.00", "last_order": "May 4, 2026"},
            {"id": "CUST-0008", "name": "Kevin Villanueva", "phone": "0928 444 6666", "email": "kevin.villanueva@email.com", "orders": 4, "spent": "₱650.00", "last_order": "Apr 29, 2026"},
        ]

    def cashier_demo_receipts(self):
        return [
            {
                "receipt_id": "RCP-000124",
                "order_id": "#ORD-000124",
                "customer": "Walk-in Customer",
                "date_time": "May 4, 2026\n10:45 AM",
                "amount": "₱425.60",
                "payment": "Cash",
                "cashier": "Juan Dela Cruz",
                "items": [("Iced Caramel Latte", 1, "₱145.00", "₱145.00"), ("Mocha Frappe", 1, "₱135.00", "₱135.00"), ("Classic Milk Tea", 1, "₱120.00", "₱120.00"), ("Pearl", 1, "₱25.00", "₱25.00")],
                "subtotal": "₱425.00",
                "discount": "- ₱20.00",
                "tax": "₱45.60",
                "tendered": "₱500.00",
                "change": "₱74.40",
            },
            {"receipt_id": "RCP-000123", "order_id": "#ORD-000123", "customer": "Maria Santos", "date_time": "May 4, 2026\n10:40 AM", "amount": "₱180.00", "payment": "GCash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000122", "order_id": "#ORD-000122", "customer": "John Dela Cruz", "date_time": "May 4, 2026\n10:35 AM", "amount": "₱310.00", "payment": "Cash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000121", "order_id": "#ORD-000121", "customer": "Walk-in Customer", "date_time": "May 4, 2026\n10:30 AM", "amount": "₱120.00", "payment": "Cash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000120", "order_id": "#ORD-000120", "customer": "Ana Reyes", "date_time": "May 4, 2026\n10:25 AM", "amount": "₱190.00", "payment": "Card", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000119", "order_id": "#ORD-000119", "customer": "Michael Tan", "date_time": "May 4, 2026\n10:20 AM", "amount": "₱285.00", "payment": "Cash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000118", "order_id": "#ORD-000118", "customer": "Liza Garcia", "date_time": "May 4, 2026\n10:15 AM", "amount": "₱150.00", "payment": "GCash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000117", "order_id": "#ORD-000117", "customer": "Kevin Villanueva", "date_time": "May 4, 2026\n10:10 AM", "amount": "₱460.00", "payment": "Cash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000116", "order_id": "#ORD-000116", "customer": "Samantha Cruz", "date_time": "May 4, 2026\n10:05 AM", "amount": "₱210.00", "payment": "GCash", "cashier": "Juan Dela Cruz"},
            {"receipt_id": "RCP-000115", "order_id": "#ORD-000115", "customer": "Mark Lopez", "date_time": "May 4, 2026\n10:00 AM", "amount": "₱175.00", "payment": "Cash", "cashier": "Juan Dela Cruz"},
        ]

    def cashier_all_snapshots(self):
        state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        snapshots = []
        current = state.get("current")
        if isinstance(current, dict):
            snapshots.append(current)
        for snapshot in state.get("history", []):
            if isinstance(snapshot, dict):
                snapshots.append(snapshot)
        return snapshots

    def cashier_live_receipts(self):
        if self._cashier_receipts_cache is not None:
            return [dict(receipt) for receipt in self._cashier_receipts_cache]

        receipts = []
        for snapshot in self.cashier_all_snapshots():
            snapshot_date = str(snapshot.get("date") or self.today_key())
            entries = snapshot.get("order_entries") or []
            for entry in entries:
                record = dict(entry or {})
                created_at = str(record.get("created_at", "")).strip()
                created_dt = QDateTime.fromString(created_at, "yyyy-MM-dd HH:mm:ss")
                if not created_dt.isValid():
                    created_dt = QDateTime.fromString(f"{snapshot_date} 00:00:00", "yyyy-MM-dd HH:mm:ss")

                order_number = str(record.get("id", "")).strip() or "0"
                numeric_order = self.safe_int(order_number)
                total_amount = self.safe_int(record.get("total_price", 0))
                payment_method = str(record.get("payment_method", "")).strip() or "Cash"
                amount_tendered = self.safe_int(record.get("amount_tendered", total_amount))
                change_amount = self.safe_int(record.get("change_amount", max(0, amount_tendered - total_amount)))
                customer_name = str(record.get("customer_name", "")).strip() or "Walk-in Customer"
                order_type = str(record.get("order_type", "")).strip() or "Dine-in"
                cashier_name = str(record.get("cashier_name", "")).strip() or self.current_user_name()
                quantity = max(1, self.safe_int(record.get("quantity", 1)))
                unit_price = total_amount / quantity if quantity else total_amount
                addons = [str(addon).strip() for addon in (record.get("addons") or []) if str(addon).strip()]
                item_rows = [
                    (
                        str(record.get("product_name", "Product")).strip() or "Product",
                        max(1, self.safe_int(record.get("quantity", 1))),
                        f"₱{total_amount:,}",
                        f"₱{total_amount:,}",
                    )
                ]
                for addon in addons:
                    item_rows.append((addon, 1, "₱0.00", "₱0.00"))

                item_rows[0] = (
                    item_rows[0][0],
                    quantity,
                    f"\u20b1{unit_price:,.2f}",
                    f"\u20b1{total_amount:,.2f}",
                )
                for index in range(1, len(item_rows)):
                    item_rows[index] = (item_rows[index][0], 1, "\u20b10.00", "\u20b10.00")

                receipts.append({
                    "receipt_id": f"RCP-{snapshot_date.replace('-', '')}-{numeric_order:04d}",
                    "order_id": f"#ORD-{snapshot_date.replace('-', '')}-{numeric_order:04d}",
                    "customer": customer_name,
                    "date_time": created_dt.toString("MMM d, yyyy\nh:mm AP") if created_dt.isValid() else f"{snapshot_date}\n{record.get('display_time', '-')}",
                    "date_time_display": created_dt.toString(f"MMM d, yyyy\nh:mm AP • {order_type}") if created_dt.isValid() else f"{snapshot_date}\n{record.get('display_time', '-')} • {order_type}",
                    "amount": f"₱{total_amount:,}",
                    "payment": payment_method,
                    "cashier": cashier_name,
                    "order_type": order_type,
                    "status": self.normalize_order_status(record.get("status")),
                    "items": item_rows,
                    "subtotal": f"₱{total_amount:,}",
                    "discount": "₱0.00",
                    "tax": "₱0.00",
                    "tendered": f"₱{total_amount:,}",
                    "change": "₱0.00",
                    "_sort_key": created_dt.toString("yyyyMMddHHmmss") if created_dt.isValid() else f"{snapshot_date}{numeric_order:04d}",
                })
                receipts[-1]["amount"] = f"\u20b1{total_amount:,.2f}"
                receipts[-1]["subtotal"] = f"\u20b1{total_amount:,.2f}"
                receipts[-1]["discount"] = "\u20b10.00"
                receipts[-1]["tax"] = "\u20b10.00"
                receipts[-1]["tendered"] = f"\u20b1{total_amount:,.2f}"
                receipts[-1]["change"] = "\u20b10.00"
                receipts[-1]["tendered"] = f"\u20b1{amount_tendered:,.2f}"
                receipts[-1]["change"] = f"\u20b1{change_amount:,.2f}"

        receipts.sort(key=lambda item: item.get("_sort_key", ""), reverse=True)
        if receipts:
            self._cashier_receipts_cache = [dict(receipt) for receipt in receipts]
            return [dict(receipt) for receipt in self._cashier_receipts_cache]
        demo_receipts = self.cashier_demo_receipts()
        self._cashier_receipts_cache = [dict(receipt) for receipt in demo_receipts]
        return [dict(receipt) for receipt in self._cashier_receipts_cache]

    def cashier_live_customers(self):
        receipts = self.cashier_live_receipts()
        customer_map = {}
        for receipt in receipts:
            name = str(receipt.get("customer", "")).strip() or "Walk-in Customer"
            key = name.lower()
            details = customer_map.setdefault(key, {
                "id": "",
                "name": name,
                "phone": "-",
                "email": "-",
                "orders": 0,
                "spent_value": 0,
                "last_order_key": "",
                "last_order": "-",
            })
            details["orders"] += 1
            details["spent_value"] += self.price_value_from_text(receipt.get("amount", "0"))
            raw_dt = str(receipt.get("date_time", "")).replace("\n", " ").strip()
            parsed_dt = QDateTime.fromString(raw_dt, "MMM d, yyyy h:mm AP")
            sort_key = parsed_dt.toString("yyyyMMddHHmmss") if parsed_dt.isValid() else raw_dt
            if sort_key >= details["last_order_key"]:
                details["last_order_key"] = sort_key
                details["last_order"] = raw_dt.split(" ", 3)[0:3]
                details["last_order"] = " ".join(details["last_order"]) if isinstance(details["last_order"], list) else raw_dt

        customers = []
        for index, (_, details) in enumerate(sorted(customer_map.items(), key=lambda item: (-item[1]["orders"], item[1]["name"])) , start=1):
            customers.append({
                "id": f"CUST-{index:04d}",
                "name": details["name"],
                "phone": details["phone"],
                "email": details["email"],
                "orders": details["orders"],
                "spent": f"₱{details['spent_value']:,}.00" if details["spent_value"] and "." not in str(details["spent_value"]) else f"₱{details['spent_value']:,}",
                "last_order": details["last_order"] if details["last_order"] != "-" else self.active_summary_date_label(),
            })

        if customers:
            return customers
        return self.cashier_demo_customers()

    def cashier_pagination_bar(self, summary_text, pages, active_page=1):
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        summary = QLabel(summary_text)
        summary.setStyleSheet("font-size:13px; color:#9a8474;")
        layout.addWidget(summary)
        layout.addStretch()

        prev_btn = self.cashier_toolbar_button("<", subtle=True, width=34)
        prev_btn.setMinimumHeight(34)
        layout.addWidget(prev_btn)

        for page in range(1, pages + 1):
            page_btn = self.cashier_toolbar_button(str(page), primary=(page == active_page), subtle=(page != active_page), width=34)
            page_btn.setMinimumHeight(34)
            layout.addWidget(page_btn)

        next_btn = self.cashier_toolbar_button(">", subtle=True, width=34)
        next_btn.setMinimumHeight(34)
        layout.addWidget(next_btn)
        return wrap

    def refresh_cashier_receipts_page(self):
        page_index = self.page_index_by_builder_name("page_cashier_receipts")
        if page_index is None or not hasattr(self, "stack") or self.stack.count() <= page_index:
            return
        self.invalidate_cashier_receipts_cache()
        self.mark_page_dirty(page_index, "page_cashier_receipts")
        if self.stack.currentIndex() == page_index:
            self._schedule_page_refresh(page_index, 0)

    def invalidate_cashier_receipts_cache(self):
        self._cashier_receipts_cache = None

    def handle_cashier_receipt_view(self, receipt):
        self.cashier_selected_receipt = dict(receipt or {})
        table = getattr(self, "cashier_receipts_table", None)
        if table is not None:
            self.refresh_cashier_receipt_row_highlight((receipt or {}).get("receipt_id"))
            self.replace_cashier_receipt_detail_card(receipt or {})
            return
        self.refresh_cashier_receipts_page()

    def cashier_receipt_print_html(self, receipt):
        def esc(value):
            return html.escape(str(value if value is not None else ""))

        items_html = "".join(
            f"""
            <tr>
                <td style="padding:4px 0; text-align:left;">{esc(item_name)}</td>
                <td style="padding:4px 0; text-align:center;">{esc(qty)}</td>
                <td style="padding:4px 0; text-align:right;">{esc(price)}</td>
                <td style="padding:4px 0; text-align:right;">{esc(amount)}</td>
            </tr>
            """
            for item_name, qty, price, amount in receipt.get("items", [])
        )
        if not items_html:
            items_html = """
            <tr>
                <td style="padding:4px 0; text-align:left;">-</td>
                <td style="padding:4px 0; text-align:center;">-</td>
                <td style="padding:4px 0; text-align:right;">-</td>
                <td style="padding:4px 0; text-align:right;">-</td>
            </tr>
            """

        meta_rows = [
            ("Receipt ID", receipt.get("receipt_id", "-")),
            ("Order ID", receipt.get("order_id", "-")),
            ("Customer", receipt.get("customer", "Walk-in Customer")),
            ("Order Type", receipt.get("order_type", "Dine-in")),
            ("Date & Time", str(receipt.get("date_time", "-")).replace("\n", " ")),
            ("Cashier", receipt.get("cashier", "-")),
        ]
        totals = [
            ("Subtotal", receipt.get("subtotal", receipt.get("amount", "-"))),
            ("TOTAL", receipt.get("amount", "-")),
            ("Payment Method", receipt.get("payment", "-")),
            ("Amount Tendered", receipt.get("tendered", "-")),
            ("Change", receipt.get("change", "-")),
        ]

        meta_html = "".join(
            f"""
            <tr>
                <td style="padding:2px 0; color:#5f4e42;">{esc(label)}</td>
                <td style="padding:2px 0; text-align:right; font-weight:700; color:#24160f;">{esc(value)}</td>
            </tr>
            """
            for label, value in meta_rows
        )
        totals_html = "".join(
            f"""
            <tr>
                <td style="padding:3px 0; color:{'#24160f' if label == 'TOTAL' else '#5f4e42'}; font-weight:{'900' if label == 'TOTAL' else '700'}; font-size:{'16px' if label == 'TOTAL' else '12px'};">{esc(label)}</td>
                <td style="padding:3px 0; text-align:right; color:{'#24160f' if label == 'TOTAL' else '#24160f'}; font-weight:{'900' if label == 'TOTAL' else '700'}; font-size:{'16px' if label == 'TOTAL' else '12px'};">{esc(value)}</td>
            </tr>
            """
            for label, value in totals
        )

        return f"""
        <html>
        <body style="font-family:'Segoe UI', Arial, sans-serif; color:#24160f; margin:18px;">
            <div style="text-align:center;">
                <div style="font-size:26px; font-weight:900;">Best Brew</div>
                <div style="font-size:11px; font-weight:700; letter-spacing:1px; color:#7d6859;">MILK TEA &amp; COFFEE</div>
                <div style="font-size:12px; margin-top:8px; color:#5f4e42;">
                    Sitio Balanoy Barangay Prenza<br>
                    09279532747
                </div>
                <div style="font-size:22px; font-weight:900; margin:14px 0 10px;">RECEIPT</div>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:12px;">{meta_html}</table>
            <hr style="border:none; border-top:1px dashed #cdb9aa; margin:10px 0;">
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
                <thead>
                    <tr>
                        <th style="text-align:left; padding:4px 0;">Item</th>
                        <th style="text-align:center; padding:4px 0;">Qty</th>
                        <th style="text-align:right; padding:4px 0;">Price</th>
                        <th style="text-align:right; padding:4px 0;">Amount</th>
                    </tr>
                </thead>
                <tbody>{items_html}</tbody>
            </table>
            <hr style="border:none; border-top:1px dashed #cdb9aa; margin:10px 0;">
            <table style="width:100%; border-collapse:collapse; font-size:12px;">{totals_html}</table>
            <div style="text-align:center; margin-top:16px; font-size:12px; color:#4d3a30;">
                Thank you and come again!<br>&hearts;
            </div>
        </body>
        </html>
        """

    def handle_cashier_receipt_print(self, receipt):
        self.cashier_selected_receipt = dict(receipt or {})
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageMargins(12, 12, 12, 12, QPrinter.Millimeter)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Receipt")
        if dialog.exec_() != QDialog.Accepted:
            self.show_notification("Print Cancelled", "Receipt printing was cancelled.", "info", 1800)
            return

        document = QTextDocument()
        document.setHtml(self.cashier_receipt_print_html(receipt))
        try:
            document.print_(printer)
            self.show_notification(
                "Print Receipt",
                f"{receipt.get('receipt_id', 'Receipt')} sent to printer.",
                "success",
                2400,
            )
        except Exception as e:
            self.show_notification("Print Error", f"Could not print receipt:\n{e}", "error", 3200)

    def cashier_receipt_detail_card(self, receipt):
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background:#fffdfa;
                border:1px solid #eadccd;
                border-radius:18px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("Receipt Details")
        title.setStyleSheet("font-size:16px; font-weight:900; color:#2e1d14;")
        close_lbl = QLabel("×")
        close_lbl.setStyleSheet("font-size:16px; color:#8a786b;")
        top.addWidget(title)
        top.addStretch()
        print_btn = self.cashier_toolbar_button("Print Receipt", subtle=True, width=138)
        print_btn.clicked.connect(lambda checked=False, item=receipt: self.handle_cashier_receipt_print(item))
        top.addWidget(print_btn)
        top.addWidget(close_lbl)
        layout.addLayout(top)

        paper = QFrame()
        paper.setStyleSheet("""
            QFrame {
                background:white;
                border:1px solid #ece2d8;
                border-radius:10px;
            }
        """)
        paper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        paper.setMinimumHeight(500)
        paper_layout = QVBoxLayout(paper)
        paper_layout.setContentsMargins(16, 12, 16, 12)
        paper_layout.setSpacing(4)

        brand = QLabel("Best Brew")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("font-size:28px; font-weight:900; color:#2f1a12; background:transparent; border:none;")
        sub = QLabel("MILK TEA & COFFEE")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size:11px; font-weight:800; color:#8c7768; letter-spacing:1px; background:transparent; border:none;")
        addr = QLabel("Sitio Balanoy Barangay Prenza\n09279532747")
        addr.setAlignment(Qt.AlignCenter)
        addr.setStyleSheet("font-size:12px; font-weight:600; color:#5e4c40; background:transparent; border:none;")
        receipt_title = QLabel("RECEIPT")
        receipt_title.setAlignment(Qt.AlignCenter)
        receipt_title.setStyleSheet("font-size:24px; font-weight:900; color:#2e1b13; margin-top:4px; background:transparent; border:none;")
        paper_layout.addWidget(brand)
        paper_layout.addWidget(sub)
        paper_layout.addWidget(addr)
        paper_layout.addWidget(receipt_title)

        meta_rows = [
            ("Receipt ID", receipt.get("receipt_id", "-")),
            ("Order ID", receipt.get("order_id", "-")),
            ("Customer", receipt.get("customer", "Walk-in Customer")),
            ("Order Type", receipt.get("order_type", "Dine-in")),
            ("Date & Time", str(receipt.get("date_time", "-")).replace("\n", "  ")),
            ("Cashier", receipt.get("cashier", "-")),
        ]
        for label_text, value_text in meta_rows:
            row = QHBoxLayout()
            left = QLabel(label_text)
            left.setStyleSheet("font-size:13px; font-weight:700; color:#6f5d51; background:transparent; border:none;")
            right = QLabel(value_text)
            right.setStyleSheet("font-size:13px; font-weight:900; color:#2a1911; background:transparent; border:none;")
            row.addWidget(left)
            row.addStretch()
            row.addWidget(right)
            paper_layout.addLayout(row)

        line = QFrame()
        line.setStyleSheet("background:#eadfd5; min-height:1px; max-height:1px; border:none;")
        paper_layout.addWidget(line)

        item_grid = QGridLayout()
        item_grid.setContentsMargins(0, 0, 0, 0)
        item_grid.setHorizontalSpacing(10)
        item_grid.setVerticalSpacing(8)
        item_grid.setColumnStretch(0, 4)
        item_grid.setColumnMinimumWidth(1, 42)
        item_grid.setColumnMinimumWidth(2, 72)
        item_grid.setColumnMinimumWidth(3, 78)

        for col, (txt, align) in enumerate([
            ("Item", Qt.AlignLeft | Qt.AlignVCenter),
            ("Qty", Qt.AlignCenter),
            ("Price", Qt.AlignRight | Qt.AlignVCenter),
            ("Amount", Qt.AlignRight | Qt.AlignVCenter),
        ]):
            lbl = QLabel(txt)
            lbl.setAlignment(align)
            lbl.setStyleSheet("font-size:13px; font-weight:900; color:#7a6558; background:transparent; border:none;")
            item_grid.addWidget(lbl, 0, col)

        for grid_row, (item_name, qty, price, amount) in enumerate(receipt.get("items", []), start=1):
            values = [
                (item_name, Qt.AlignLeft | Qt.AlignVCenter),
                (str(qty), Qt.AlignCenter),
                (price, Qt.AlignRight | Qt.AlignVCenter),
                (amount, Qt.AlignRight | Qt.AlignVCenter),
            ]
            for col, (text, align) in enumerate(values):
                lbl = QLabel(str(text))
                lbl.setAlignment(align)
                lbl.setStyleSheet("font-size:13px; font-weight:700; color:#2a1911; background:transparent; border:none;")
                item_grid.addWidget(lbl, grid_row, col)

        paper_layout.addLayout(item_grid)

        line2 = QFrame()
        line2.setStyleSheet("background:#eadfd5; min-height:1px; max-height:1px; border:none;")
        paper_layout.addWidget(line2)

        totals = [
            ("Subtotal", receipt.get("subtotal", receipt.get("amount", "-"))),
            ("TOTAL", receipt.get("amount", "-")),
            ("Payment Method", receipt.get("payment", "-")),
            ("Amount Tendered", receipt.get("tendered", "-")),
            ("Change", receipt.get("change", "-")),
        ]
        for label_text, value_text in totals:
            row = QHBoxLayout()
            left = QLabel(label_text)
            left.setStyleSheet("font-size:13px; font-weight:700; color:#5f4e42; background:transparent; border:none;" if label_text != "TOTAL" else "font-size:20px; font-weight:900; color:#28170f; background:transparent; border:none;")
            right = QLabel(value_text)
            right.setStyleSheet("font-size:13px; font-weight:900; color:#2a1911; background:transparent; border:none;" if label_text != "TOTAL" else "font-size:20px; font-weight:900; color:#28170f; background:transparent; border:none;")
            row.addWidget(left)
            row.addStretch()
            row.addWidget(right)
            paper_layout.addLayout(row)

        thanks = QLabel("Thank you and come again!\n♥")
        thanks.setAlignment(Qt.AlignCenter)
        thanks.setStyleSheet("font-size:12px; font-weight:700; color:#4d3a30; margin-top:8px; background:transparent; border:none;")
        paper_layout.addWidget(thanks)
        layout.addWidget(paper, 1)
        return card

    def configure_cashier_dashboard_touch_targets(self, cards, alerts_layout=None, activity_layout=None, products_layout=None):
        metric_routes = {
            (0, 0): "page_cashier_products",
            (0, 1): "page_cashier_orders",
            (0, 2): "page_cashier_receipts",
            (0, 3): "page_cashier_products",
        }
        for position, builder_name in metric_routes.items():
            item = cards.itemAtPosition(*position)
            if not item or not item.widget():
                continue
            widget = item.widget()
            widget.setFixedHeight(118)
            self.make_dashboard_action_clickable(widget, lambda target=builder_name: self.switch_to_builder(target))

        if alerts_layout is not None:
            for index in range(1, alerts_layout.count()):
                item = alerts_layout.itemAt(index)
                widget = item.widget()
                if widget is not None:
                    self.make_dashboard_action_clickable(widget, self.handle_quick_new_order)

        if activity_layout is not None:
            for index in range(1, activity_layout.count()):
                item = activity_layout.itemAt(index)
                widget = item.widget()
                if widget is not None:
                    self.make_dashboard_action_clickable(widget, self.handle_quick_view_reports)

        if products_layout is not None:
            for index in range(1, products_layout.count()):
                item = products_layout.itemAt(index)
                widget = item.widget()
                if widget is not None:
                    self.make_dashboard_action_clickable(widget, self.handle_quick_new_order)

    def cashier_placeholder_page(self, title, subtitle):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self.page_header(title, subtitle))

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background:#fff8f2;
                border:1px solid #ead8c8;
                border-radius:22px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 26)
        card_layout.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:22px; font-weight:900; color:#2d1b13;")
        note_lbl = QLabel("This cashier section is ready in the sidebar. We can connect the exact workflow you want next.")
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet("font-size:14px; color:#7b6659;")
        card_layout.addWidget(title_lbl)
        card_layout.addWidget(note_lbl)
        layout.addWidget(card)
        return self.build_scroll_page(content)

    def page_cashier_products(self):
        return self.page_products()

    def page_cashier_new_order(self):
        return self.page_cashier_products()

    def page_cashier_orders(self):
        return self.page_orders()

    def page_cashier_customers(self):
        customers = self.cashier_live_customers()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self.page_header("Customers", "View and manage customer information."))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addStretch()
        toolbar.addWidget(self.cashier_search_field("Search customer...", 240))
        toolbar.addWidget(self.cashier_toolbar_button("Filter", subtle=True, width=92))
        toolbar.addWidget(self.cashier_toolbar_button("+  Add Customer", primary=True, width=150))
        layout.addLayout(toolbar)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background:#fffdf9;
                border:1px solid #ecddd0;
                border-radius:20px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(12)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setRowCount(len(customers))
        table.setHorizontalHeaderLabels(["Customer ID", "Name", "Phone Number", "Email", "Total Orders", "Total Spent", "Last Order", "Actions"])
        table.setStyleSheet("""
            QTableWidget {
                background:transparent;
                border:none;
                gridline-color:#f0e4da;
                color:#2e1d14;
                font-size:13px;
                selection-background-color:#f7ebdf;
                alternate-background-color:#fffaf5;
            }
            QHeaderView::section {
                background:#fffdf9;
                color:#6f5646;
                border:none;
                border-bottom:1px solid #eee1d6;
                padding:14px 10px;
                font-size:13px;
                font-weight:900;
                text-align:left;
            }
        """)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.horizontalHeader().setStretchLastSection(False)
        widths = [120, 140, 130, 210, 100, 110, 120, 120]
        for col, width in enumerate(widths):
            table.setColumnWidth(col, width)
        table.verticalHeader().setDefaultSectionSize(52)

        for row, customer in enumerate(customers):
            values = [
                customer["id"], customer["name"], customer["phone"], customer["email"],
                str(customer["orders"]), customer["spent"], customer["last_order"]
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if col in {1, 4, 5, 6} else Qt.AlignLeft))
                table.setItem(row, col, item)

            action_wrap = QWidget()
            action_layout = QHBoxLayout(action_wrap)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.addWidget(self.cashier_toolbar_button("View", subtle=True, width=68))
            action_layout.addWidget(self.cashier_toolbar_button("⋮", subtle=True, width=34))
            table.setCellWidget(row, 7, action_wrap)

        card_layout.addWidget(table)
        card_layout.addWidget(self.cashier_pagination_bar(f"Showing 1 to {len(customers)} of {len(customers)} customers", 1, 1))
        layout.addWidget(card)
        return self.build_scroll_page(content)

    def page_cashier_receipts(self):
        all_receipts = self.cashier_live_receipts()
        receipts = self.filter_cashier_receipts(all_receipts)
        selected_receipt_id = str((getattr(self, "cashier_selected_receipt", {}) or {}).get("receipt_id", "")).strip()
        featured = next((receipt for receipt in receipts if receipt.get("receipt_id") == selected_receipt_id), receipts[0] if receipts else {
            "receipt_id": "-",
            "order_id": "-",
            "customer": "No matching receipt",
            "order_type": "-",
            "date_time": "-",
            "amount": "₱0.00",
            "payment": "-",
            "cashier": "-",
            "items": [],
            "subtotal": "₱0.00",
            "discount": "₱0.00",
            "tax": "₱0.00",
            "tendered": "₱0.00",
            "change": "₱0.00",
        })

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 12, 18, 18)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        header_wrap = QWidget()
        header_layout = QHBoxLayout(header_wrap)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title = QLabel("Receipts")
        title.setStyleSheet("font-size:28px; font-weight:900; color:#20150f;")
        subtitle = QLabel("View and manage all receipts.")
        subtitle.setStyleSheet("font-size:16px; color:#8c796d;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col, 1)
        layout.addWidget(header_wrap)

        split = QHBoxLayout()
        split.setSpacing(14)

        left_card = QFrame()
        left_card.setObjectName("card")
        left_card.setStyleSheet("""
            QFrame#card {
                background:#fffdf9;
                border:1px solid #ecddd0;
                border-radius:20px;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 12, 14, 12)
        left_layout.setSpacing(8)

        filters = QHBoxLayout()
        filters.setSpacing(12)
        receipt_dates = [str(receipt.get("date_time", "")).replace("\n", " ").strip() for receipt in receipts]
        first_date = receipt_dates[-1].split(" ", 3)[:3] if receipt_dates else [self.active_summary_date_label()]
        last_date = receipt_dates[0].split(" ", 3)[:3] if receipt_dates else [self.active_summary_date_label()]
        filters.addWidget(self.cashier_toolbar_button(f"{' '.join(first_date)} - {' '.join(last_date)}", subtle=True, width=230))
        filters.addWidget(self.cashier_toolbar_button("All Payment Methods", subtle=True, width=190))
        search_field = self.cashier_search_field("Search receipt, order ID, customer...", 300)
        search_field.setText(self.receipt_search_query())
        search_field.textChanged.connect(self.set_receipt_search_query)
        self.cashier_receipt_search_input = search_field
        filters.addWidget(search_field, 1)
        filters.addWidget(self.cashier_toolbar_button("Filter", subtle=True, width=96))
        left_layout.addLayout(filters)

        table = QTableWidget()
        table.setColumnCount(9)
        table.setRowCount(len(all_receipts))
        table.setHorizontalHeaderLabels(["Receipt ID", "Order ID", "Customer", "Date & Time", "Order Type", "Amount", "Payment", "Cashier", "Actions"])
        table.setStyleSheet("""
            QTableWidget {
                background:transparent;
                border:none;
                gridline-color:#f0e4da;
                color:#3a281d;
                font-size:15px;
                selection-background-color:#f7ebdf;
                alternate-background-color:#fffaf5;
            }
            QHeaderView::section {
                background:#fffdf9;
                color:#6f5646;
                border:none;
                border-bottom:1px solid #eee1d6;
                padding:14px 10px;
                font-size:15px;
                font-weight:900;
            }
            QTableWidget::item {
                border-bottom:1px solid #f3e8de;
                padding:8px 8px;
            }
        """)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(74)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        table.setColumnWidth(0, 118)
        table.setColumnWidth(1, 128)
        table.setColumnWidth(3, 132)
        table.setColumnWidth(4, 108)
        table.setColumnWidth(5, 78)
        table.setColumnWidth(7, 96)
        table.setColumnWidth(8, 168)
        table.verticalHeader().setDefaultSectionSize(64)
        table.setMinimumHeight(670)
        self.cashier_receipts_source = list(all_receipts)
        self.cashier_receipts_table = table

        for row, receipt in enumerate(all_receipts):
            values = [
                receipt["receipt_id"], receipt["order_id"], receipt["customer"], receipt["date_time"],
                receipt.get("order_type", "Dine-in"), receipt["amount"], "", receipt["cashier"]
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 5:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                elif col in {2, 4, 7}:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if receipt.get("receipt_id") == featured.get("receipt_id"):
                    item.setBackground(QColor("#fdf4eb"))
                table.setItem(row, col, item)

            payment_badge = self.cashier_receipt_payment_badge(receipt.get("payment", "Cash"))
            payment_wrap = QWidget()
            payment_wrap.setStyleSheet("background:transparent; border:none;")
            payment_layout = QHBoxLayout(payment_wrap)
            payment_layout.setContentsMargins(0, 0, 0, 0)
            payment_layout.setSpacing(0)
            payment_layout.addWidget(payment_badge, 0, Qt.AlignCenter)
            table.setCellWidget(row, 6, payment_wrap)

            actions_wrap = QWidget()
            actions_wrap.setStyleSheet("background:transparent; border:none;")
            actions_layout = QHBoxLayout(actions_wrap)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(4)
            view_btn = self.cashier_receipt_action_button("View", 76, "view")
            view_btn.setToolTip("View receipt")
            view_btn.clicked.connect(lambda checked=False, item=receipt: self.handle_cashier_receipt_view(item))
            actions_layout.addWidget(view_btn)
            table.setCellWidget(row, 8, actions_wrap)

        left_layout.addWidget(table)
        split.addWidget(left_card, 3)

        right_panel = QWidget()
        self.cashier_receipt_detail_layout = QVBoxLayout(right_panel)
        self.cashier_receipt_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.cashier_receipt_detail_layout.setSpacing(0)
        self.cashier_receipt_detail_widget = None
        split.addWidget(right_panel, 1)
        self.replace_cashier_receipt_detail_card(featured)

        layout.addLayout(split)
        self.apply_cashier_receipt_table_filter()
        return self.build_scroll_page(content)

    def system_prefers_dark(self):
        app = QApplication.instance()
        if app is None:
            return False
        return app.palette().window().color().lightness() < 128

    def apply_system_theme(self):
        dark_mode = self.system_prefers_dark()
        extra_dark = """
            QWidget {
                background: #1c1714;
                color: #f0e3d4;
            }

            QLabel {
                color: #f0e3d4;
            }

            QFrame#card {
                background: #2a221d;
                border: 1px solid #4a3a31;
            }

            QLineEdit, QTableWidget {
                background: #241d18;
                color: #f2e5d7;
                border: 1px solid #534136;
            }

            QHeaderView::section {
                background: #342922;
                color: #f1e4d6;
                border-right: 1px solid #4f3d32;
            }
        """ if dark_mode else ""

        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI';
                background: #f6f1ea;
                color: #2f1b12;
            }

            QLabel {
                background: transparent;
                color: #2f1b12;
                border: none;
                padding: 0;
                margin: 0;
            }

            QFrame#sidebar {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #663825,
                    stop:0.5 #4d2a1f,
                    stop:1 #3b221a
                );
                border: none;
            }

            QFrame#brandBadge {
                background: transparent;
            }

            QLabel#brandIcon {
                background: rgba(255, 248, 241, 0.10);
                border: 1px solid rgba(255, 245, 236, 0.28);
                border-radius: 30px;
                min-width: 60px;
                max-width: 60px;
                min-height: 60px;
                max-height: 60px;
                color: #fff8f1;
                font-size: 22px;
                font-weight: 900;
                padding: 0;
            }

            QLabel#brandTitle {
                color: white;
                font-size: 28px;
                font-weight: 900;
                background: transparent;
            }

            QLabel#brandSub {
                color: #e8d5c6;
                font-size: 16px;
                background: transparent;
            }

            QPushButton#navButton {
                background: rgba(255, 248, 241, 0.03);
                color: #fff8f1;
                border: 1px solid transparent;
                border-radius: 18px;
                padding: 18px 20px;
                text-align: left;
                font-size: 18px;
                font-weight: 800;
            }

            QPushButton#navButton:hover {
                background: rgba(200, 135, 90, 0.18);
                border: 1px solid rgba(255, 236, 223, 0.12);
            }

            QPushButton#navButtonActive {
                background: #8f573d;
                color: white;
                border: 1px solid rgba(255, 236, 223, 0.14);
                border-radius: 18px;
                padding: 18px 20px;
                text-align: left;
                font-size: 18px;
                font-weight: 900;
            }

            QPushButton#exitBtn {
                background: transparent;
                color: white;
                border: 1px solid transparent;
                border-radius: 16px;
                padding: 16px 18px;
                text-align: left;
                font-size: 17px;
                font-weight: 800;
            }

            QPushButton#exitBtn:hover {
                background: rgba(200, 135, 90, 0.18);
                border: 1px solid rgba(255, 236, 223, 0.12);
            }

            QLabel#sidebarDecor {
                color: rgba(173, 111, 74, 0.45);
                font-size: 34px;
                background: transparent;
            }

            QFrame#sidebarDivider {
                background: rgba(255, 236, 223, 0.18);
                min-height: 1px;
                max-height: 1px;
                border: none;
            }

            QFrame#cashierProfileCard {
                background: #7a472f;
                border: 1px solid rgba(255, 236, 223, 0.16);
                border-radius: 18px;
            }

            QLabel#cashierAvatar {
                background: rgba(255, 255, 255, 0.08);
                color: #fff8f1;
                border: 1px solid rgba(255, 236, 223, 0.20);
                border-radius: 28px;
                min-width: 56px;
                max-width: 56px;
                min-height: 56px;
                max-height: 56px;
                font-size: 16px;
                font-weight: 900;
            }

            QLabel#cashierName {
                color: #fff8f1;
                font-size: 15px;
                font-weight: 800;
            }

            QLabel#cashierRole {
                color: #d9c4b3;
                font-size: 12px;
                font-weight: 600;
            }

            QLabel#cashierStatus {
                color: #dff3de;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(223, 243, 222, 0.18);
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
            }

            QFrame#card {
                background: #f8efe4;
                border: 1px solid #ead7c5;
                border-radius: 18px;
            }

            QLabel#pageTitle {
                font-size: 28px;
                font-weight: 900;
                color: #1f160f;
                border: none;
            }

            QLabel#pageSub {
                font-size: 14px;
                color: #7a6e66;
                border: none;
            }

            QLabel#cardTitle {
                font-size: 14px;
                color: #776b63;
                background: transparent;
                border: none;
            }

            QLabel#cardValue {
                font-size: 24px;
                font-weight: 900;
                color: #1f160f;
                background: transparent;
                border: none;
            }

            QLabel#sectionTitle {
                font-size: 20px;
                font-weight: 800;
                color: #2f1b12;
                background: transparent;
                border: none;
            }

            QLabel#muted {
                font-size: 14px;
                color: #7a6e66;
                background: transparent;
                border: none;
            }

            QPushButton#smallBtn {
                background: #2f1b12;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 700;
            }

            QPushButton#smallBtn:hover {
                background: #5b3423;
            }

            QPushButton#lightBtn {
                background: #f7ecdf;
                color: #2f1b12;
                border: 1px solid #dcc8b7;
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 700;
            }

            QPushButton#lightBtn:hover {
                background: #f2e3d3;
            }

            QLineEdit {
                background: #fbf3ea;
                border: 1px solid #dccdbf;
                border-radius: 12px;
                padding: 12px 14px;
                font-size: 14px;
            }

            QTableWidget {
                background: #fbf3ea;
                border: 1px solid #e0cfc0;
                border-radius: 14px;
                gridline-color: #ead8c8;
                font-size: 15px;
            }

            QHeaderView::section {
                background: #f1e4d4;
                color: #3a2418;
                padding: 14px 10px;
                border: none;
                border-right: 1px solid #e0d1c1;
                font-weight: 800;
                font-size: 14px;
            }
        """ + extra_dark)

    def nav_icon(self, filename):
        return QIcon(os.path.join(PROJECT_ROOT, "assets", "sidebar", filename))

    def fallback_inventory_data(self):
        return [
            {
                "id": None,
                "name": "Black Tea Leaves",
                "category": "Tea Base",
                "stock": "15 kg",
                "reorder": "10 kg",
                "status": "Good",
                "date": "-",
                "accent": "#6f4a31",
                "icon": "BT",
            },
            {
                "id": None,
                "name": "Fresh Milk",
                "category": "Dairy",
                "stock": "5 liters",
                "reorder": "8 liters",
                "status": "Low",
                "date": "-",
                "accent": "#6f4a31",
                "icon": "FM",
            },
            {
                "id": None,
                "name": "Tapioca Pearls",
                "category": "Add-on",
                "stock": "0 kg",
                "reorder": "6 kg",
                "status": "Out",
                "date": "-",
                "accent": "#6f4a31",
                "icon": "TP",
            },
        ]

    def load_products_from_database(self):
        try:
            products = self.controller.get_products()
            return self.ensure_product_images_are_portable(products)

        except Exception as e:
            print(f"Cannot load products: {e}")
            return []

    def ensure_product_images_are_portable(self, products):
        normalized_products = []
        for product in products:
            portable_image = import_product_image(product.get("image", ""))
            if portable_image and portable_image != product.get("image", "") and product.get("id"):
                try:
                    self.controller.update_product(product["id"], {
                        "name": product.get("name", "New Product"),
                        "category": product.get("category", "Classic"),
                        "price_text": product.get("price_text", "0"),
                        "desc": product.get("desc", "No description"),
                        "image": portable_image,
                        "available": product.get("available", True),
                    })
                    product = {**product, "image": portable_image}
                except Exception as migration_error:
                    print(f"Cannot localize image for {product.get('name', 'product')}: {migration_error}")
            normalized_products.append(product)
        return normalized_products

    def load_order_addons(self):
        try:
            rows = self.controller.get_addons()
            addons = []
            for row in rows:
                addons.append({
                    "id": row.get("id"),
                    "name": row.get("name", ""),
                    "price": row.get("price", 0),
                })
            if addons:
                return addons
        except Exception as e:
            print(f"Cannot load addons: {e}")

        return [
            {"id": None, "name": "Pearls", "price": 15},
            {"id": None, "name": "Pudding", "price": 15},
            {"id": None, "name": "Jelly", "price": 15},
            {"id": None, "name": "Cream Cheese", "price": 15},
        ]

    def build_database_addon_items(self, order_config):
        selected_addon_names = {
            str(addon_name).strip()
            for addon_name in (order_config.get("addons", []) or [])
            if str(addon_name).strip()
        }
        if not selected_addon_names:
            return []

        quantity = max(1, int(order_config.get("quantity", 1) or 1))
        addon_items = []
        for addon in self.load_order_addons():
            addon_name = str(addon.get("name", "")).strip()
            if addon_name not in selected_addon_names:
                continue
            addon_price = self.safe_int(addon.get("price", 0))
            addon_id = addon.get("id")
            addon_items.append({
                "addon_id": addon_id,
                "quantity": quantity,
                "line_total": addon_price * quantity,
            })
        return addon_items

    def persist_products(self):
        self.products = self.load_products_from_database()

    def update_products_section_title(self):
        if hasattr(self, "products_card"):
            title_label = self.products_card.findChild(QLabel, "sectionTitle")
            if title_label:
                title_label.setText(f"Products ({len(self.products)})")

    def today_key(self):
        return date.today().isoformat()

    def current_hour(self):
        return QDateTime.currentDateTime().time().hour()

    def load_shop_schedule_from_database(self):
        fallback = {
            "opening_time": "08:00:00",
            "closing_time": "23:00:00",
            "shop_status": "CLOSED",
        }
        try:
            schedule = self.controller.get_shop_schedule() or {}
            fallback.update(schedule)
        except Exception as e:
            print(f"Cannot load shop schedule: {e}")
        return fallback

    def _schedule_time(self, key, fallback):
        raw = str((self.shop_schedule or {}).get(key) or fallback)
        parsed = QTime.fromString(raw, "HH:mm:ss")
        if not parsed.isValid():
            parsed = QTime.fromString(raw, "H:mm:ss")
        if not parsed.isValid():
            parsed = QTime.fromString(fallback, "HH:mm:ss")
        return parsed

    def active_summary_date_key(self):
        state = getattr(self, "order_summary_state", None) or {}
        current = state.get("current") or {}
        return str(current.get("date") or state.get("current_date") or self.today_key())

    def active_summary_date_label(self):
        summary_date = self.active_summary_date_key()
        parsed = QDateTime.fromString(summary_date, "yyyy-MM-dd")
        if parsed.isValid():
            return parsed.toString("MMMM d, yyyy")
        return summary_date

    def should_rollover_order_summary(self):
        current_date = self.active_summary_date_key()
        return (
            current_date != self.today_key() and
            self.current_hour() >= self.store_open_hour()
        )

    def store_open_hour(self):
        return self._schedule_time("opening_time", "08:00:00").hour()

    def store_close_hour(self):
        return self._schedule_time("closing_time", "23:00:00").hour()

    def store_hours_label(self):
        opening = self._schedule_time("opening_time", "08:00:00").toString("h:mm AP")
        closing = self._schedule_time("closing_time", "23:00:00").toString("h:mm AP")
        return f"{opening} - {closing}"

    def summary_history_template(self):
        return {"current_date": self.today_key(), "current": {}, "history": []}

    def empty_order_summary_snapshot(self, summary_date=None):
        target_date = summary_date or self.today_key()
        return {
            "date": target_date,
            "order_rows": self.build_default_order_rows(),
            "daily_product_sales": {},
            "daily_size_counts": {"solo": 0, "large": 0},
            "order_entries": [],
        }

    def order_entry_date_key(self, entry, fallback_date=None):
        created_at = str((entry or {}).get("created_at", "")).strip()
        if len(created_at) >= 10:
            raw_date = created_at[:10]
            if QDateTime.fromString(raw_date, "yyyy-MM-dd").isValid():
                return raw_date
        return str(fallback_date or self.today_key())

    def rebuild_snapshot_from_entries(self, summary_date, entries):
        snapshot = self.empty_order_summary_snapshot(summary_date)
        rows = [list(row[:8]) for row in snapshot["order_rows"]]
        row_lookup = {row[0]: row for row in rows if row}
        count_column_map = {
            "milk": 1,
            "fruit": 2,
            "iced_coffee": 3,
            "milkshake": 4,
            "cream_base": 5,
        }

        normalized_entries = self.controller.renumber_order_entries(entries or [])
        for entry in normalized_entries:
            slot_label = str(entry.get("slot", "")).strip()
            row = row_lookup.get(slot_label)
            if row is not None:
                quantity = max(1, self.safe_int(entry.get("quantity", 1)))
                total_price = self.safe_int(entry.get("total_price", 0))
                category_key = self.normalize_order_category(entry.get("category", ""), entry.get("product_name", ""))
                count_col = count_column_map.get(category_key, 1)
                row[count_col] = str(self.safe_int(row[count_col]) + quantity)
                row[6] = str(self.safe_int(row[6]) + quantity)
                row[7] = str(self.safe_int(row[7]) + total_price)

            product_name = str(entry.get("product_name", "")).strip()
            if product_name:
                snapshot["daily_product_sales"][product_name] = snapshot["daily_product_sales"].get(product_name, 0) + max(1, self.safe_int(entry.get("quantity", 1)))

            size_key = "large" if str(entry.get("size", "")).strip().lower() == "large" else "solo"
            snapshot["daily_size_counts"][size_key] = snapshot["daily_size_counts"].get(size_key, 0) + max(1, self.safe_int(entry.get("quantity", 1)))

        snapshot["order_rows"] = rows
        snapshot["order_entries"] = normalized_entries
        return snapshot

    def normalize_order_summary_state(self, state):
        current = state.get("current") if isinstance(state.get("current"), dict) else {}
        history = state.get("history") if isinstance(state.get("history"), list) else []
        current_date = str(state.get("current_date") or current.get("date") or self.today_key())
        grouped_entries = {}

        snapshots = []
        if current:
            snapshots.append(current)
        snapshots.extend([entry for entry in history if isinstance(entry, dict)])

        for snapshot in snapshots:
            snapshot_date = str(snapshot.get("date") or current_date or self.today_key())
            for entry in snapshot.get("order_entries") or []:
                entry_date = self.order_entry_date_key(entry, snapshot_date)
                grouped_entries.setdefault(entry_date, []).append(dict(entry or {}))

        normalized_snapshots = {
            date_key: self.rebuild_snapshot_from_entries(date_key, entries)
            for date_key, entries in grouped_entries.items()
        }

        if current_date not in normalized_snapshots:
            normalized_snapshots[current_date] = self.empty_order_summary_snapshot(current_date)

        state["current_date"] = current_date
        state["current"] = normalized_snapshots.pop(current_date)
        state["history"] = [normalized_snapshots[key] for key in sorted(normalized_snapshots.keys(), reverse=True)][:60]
        return state

    def migrate_misaligned_current_entries(self):
        state = getattr(self, "order_summary_state", None)
        if not isinstance(state, dict):
            return

        active_date = self.active_summary_date_key()
        current_entries = list(getattr(self, "order_entries", []) or [])
        if not current_entries:
            return

        grouped_current_entries = {}
        for entry in current_entries:
            entry_date = self.order_entry_date_key(entry, active_date)
            grouped_current_entries.setdefault(entry_date, []).append(dict(entry or {}))

        if set(grouped_current_entries.keys()) == {active_date}:
            return

        history_by_date = {}
        for snapshot in state.get("history", []):
            if not isinstance(snapshot, dict):
                continue
            snapshot_date = str(snapshot.get("date") or "").strip()
            if snapshot_date:
                history_by_date[snapshot_date] = snapshot

        for date_key, entries in grouped_current_entries.items():
            rebuilt_snapshot = self.rebuild_snapshot_from_entries(date_key, entries)
            if date_key == active_date:
                state["current"] = rebuilt_snapshot
            else:
                history_by_date[date_key] = rebuilt_snapshot

        if active_date not in grouped_current_entries:
            state["current"] = self.empty_order_summary_snapshot(active_date)

        state["current_date"] = active_date
        state["history"] = [history_by_date[key] for key in sorted(history_by_date.keys(), reverse=True) if key != active_date][:60]
        self.order_summary_state = state
        self.apply_order_summary_snapshot(state.get("current"))
        self.save_order_summary_state(state)

    def load_order_summary_state(self):
        state = self.summary_history_template()
        if os.path.exists(self.order_summary_storage_path):
            try:
                with open(self.order_summary_storage_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    state.update(loaded)
            except Exception:
                state = self.summary_history_template()

        current = state.get("current") or {}
        current_date = str(state.get("current_date") or current.get("date") or self.today_key())

        if not current:
            current = self.empty_order_summary_snapshot(current_date)
        elif not current.get("date"):
            current["date"] = current_date

        state["current_date"] = current_date
        state["current"] = current
        state = self.normalize_order_summary_state(state)
        self.apply_order_summary_snapshot(state.get("current"))
        self.save_order_summary_state(state)
        return state

    def rollover_order_summary_if_needed(self):
        state = getattr(self, "order_summary_state", None)
        if state is None:
            self.order_summary_state = self.load_order_summary_state()
            state = self.order_summary_state
        if not self.should_rollover_order_summary():
            return
        current = state.get("current") or {}
        history = state.get("history", [])
        if current:
            history.insert(0, current)
        state["history"] = history[:60]
        state["current_date"] = self.today_key()
        state["current"] = self.empty_order_summary_snapshot(self.today_key())
        self.apply_order_summary_snapshot(state["current"])
        self.save_order_summary_state(state)

    def apply_order_summary_snapshot(self, snapshot):
        if not snapshot:
            snapshot = self.empty_order_summary_snapshot()
        stored_rows = snapshot.get("order_rows") or self.build_default_order_rows()
        normalized_rows = []
        default_rows = self.build_default_order_rows()
        for index, default_row in enumerate(default_rows):
            source_row = stored_rows[index] if index < len(stored_rows) else default_row
            normalized = list(source_row[:8]) + ["0"] * max(0, 8 - len(source_row[:8]))
            normalized_rows.append(normalized[:8])
        self.order_rows = normalized_rows
        self.daily_product_sales = dict(snapshot.get("daily_product_sales") or {})
        self.daily_size_counts = dict(snapshot.get("daily_size_counts") or {"solo": 0, "large": 0})
        self.daily_size_counts.setdefault("solo", 0)
        self.daily_size_counts.setdefault("large", 0)
        self.order_entries = self.controller.renumber_order_entries(snapshot.get("order_entries") or [])

    def build_current_order_summary_snapshot(self):
        if hasattr(self, "orders_table"):
            rows = []
            for row in range(self.order_data_row_count()):
                row_values = []
                for col in range(8):
                    item = self.orders_table.item(row, col)
                    row_values.append(item.text() if item else "0")
                rows.append(row_values)
        else:
            rows = [list(row[:8]) for row in self.order_rows]
        return {
            "date": self.active_summary_date_key(),
            "order_rows": rows,
            "daily_product_sales": dict(self.daily_product_sales),
            "daily_size_counts": dict(self.daily_size_counts),
            "order_entries": list(getattr(self, "order_entries", [])),
        }

    def save_order_summary_state(self, state=None):
        if state is None:
            state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        snapshot = self.build_current_order_summary_snapshot()
        state["current_date"] = snapshot.get("date", self.today_key())
        state["current"] = snapshot
        self.invalidate_cashier_receipts_cache()
        try:
            with open(self.order_summary_storage_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
        except Exception:
            pass

    def persist_order_summary_progress(self):
        self.order_summary_state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        self.save_order_summary_state(self.order_summary_state)

    def export_order_summary_report(self):
        self.persist_order_summary_progress()
        export_dir = os.path.join(PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_date = self.active_summary_date_key()
        export_path = build_unique_export_path(export_dir, "bestbrew_report", export_date, ".doc")
        state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        current = state.get("current") or self.build_current_order_summary_snapshot()
        history = state.get("history", [])[:60]

        lines = [
            "BEST BREW EXPORT REPORT",
            f"Generated: {QDateTime.currentDateTime().toString('MMMM d, yyyy h:mm AP')}",
            "",
            "ORDER SUMMARY DOCUMENT",
            "",
        ]

        for row in current.get("order_rows", []):
            if len(row) >= 8:
                lines.append(
                    f"{row[0]} | Milk Tea: {row[1]} | Fruit Tea: {row[2]} | "
                    f"Iced Coffee: {row[3]} | Milkshake: {row[4]} | Cream Base: {row[5]} | "
                    f"Total: {row[6]} | Revenue: ₱{self.safe_int(row[7]):,}"
                )

        lines.extend(["", "Recent Saved Daily Receipts:"])
        for entry in history:
            rows = entry.get("order_rows", [])
            total_orders = sum(self.safe_int(r[6]) for r in rows if len(r) > 6)
            total_revenue = sum(self.safe_int(r[7]) for r in rows if len(r) > 7)
            lines.append(f"{entry.get('date', '-')} | Orders: {total_orders} | Revenue: ₱{total_revenue:,}")

        with open(export_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        self.show_notification("Export Complete", f"Report exported successfully:\n{export_path}", "success", 3200)

    def export_order_summary_doc(self):
        export_path = self.export_admin_word_image_report(show_notification=False)
        if export_path:
            self.show_notification(
                "Export Complete",
                f"Word report exported successfully:\n{export_path}",
                "success",
                4200,
            )

    def _build_export_report_html_styled(self):
        self.persist_order_summary_progress()
        live = self.collect_live_system_data()
        state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        current = state.get("current") or self.build_current_order_summary_snapshot()

        def money(value):
            return f"PHP {int(value):,}"

        def section_bar(number, title, continued=False):
            suffix = " (CONTINUED)" if continued else ""
            return f"<div class='section-bar'>{number}) {title}{suffix}</div>"

        def status_badge(status):
            normalized = str(status or "").strip().lower()
            if normalized == "good":
                badge_class = "good"
            elif normalized == "low":
                badge_class = "low"
            else:
                badge_class = "out"
            return f"<span class='status-pill {badge_class}'>{status}</span>"

        def build_order_rows_table(rows):
            body = []
            for row in rows:
                if len(row) >= 8:
                    body.append(
                        "<tr>"
                        f"<td>{row[0]}</td>"
                        f"<td>{row[1]}</td>"
                        f"<td>{row[2]}</td>"
                        f"<td>{row[3]}</td>"
                        f"<td>{row[4]}</td>"
                        f"<td>{row[5]}</td>"
                        f"<td>{row[6]}</td>"
                        f"<td>{money(self.safe_int(row[7]))}</td>"
                        "</tr>"
                    )
            return "".join(body) or "<tr><td colspan='8' class='empty-state'>No order summary recorded.</td></tr>"

        def build_inventory_table_rows(items):
            rows = []
            for item in items:
                rows.append(
                    "<tr>"
                    f"<td>{item.get('name', '-')}</td>"
                    f"<td>{item.get('category', '-')}</td>"
                    f"<td>{item.get('stock', '-')}</td>"
                    f"<td>{item.get('reorder', '-')}</td>"
                    f"<td>{status_badge(item.get('status', '-'))}</td>"
                    "</tr>"
                )
            return "".join(rows) or "<tr><td colspan='5' class='empty-state'>No inventory data available.</td></tr>"

        def build_top_products_rows(products):
            rows = []
            for product in products[:10]:
                rows.append(
                    "<tr>"
                    f"<td>{product.get('name', '-')}</td>"
                    f"<td>{product.get('subtitle', '-')}</td>"
                    f"<td>{product.get('units', 0)}</td>"
                    f"<td>{money(product.get('revenue', 0))}</td>"
                    "</tr>"
                )
            return "".join(rows) or "<tr><td colspan='4' class='empty-state'>No product sales yet.</td></tr>"

        def summary_card(icon_html, label, value, subtext, accent_class):
            return (
                f"<td><div class='summary-card {accent_class}'>"
                f"<div class='summary-icon'>{icon_html}</div>"
                f"<div class='summary-label'>{label}</div>"
                f"<div class='summary-value'>{value}</div>"
                f"<div class='summary-sub'>{subtext}</div>"
                "</div></td>"
            )

        inventory_items = list(getattr(self, "inventory_items", []))
        first_inventory_page = inventory_items[:32]
        second_inventory_page = inventory_items[32:]

        all_receipts = [current]
        receipt_blocks = []
        for index, entry in enumerate(all_receipts, start=1):
            rows = entry.get("order_rows", [])
            total_orders = sum(self.safe_int(r[6]) for r in rows if len(r) > 6)
            total_revenue = sum(self.safe_int(r[7]) for r in rows if len(r) > 7)
            top_products = entry.get("daily_product_sales", {}) or {}
            top_products_text = ", ".join(
                f"{name} ({count})" for name, count in sorted(top_products.items(), key=lambda item: (-item[1], item[0]))[:5]
            ) or "None"
            receipt_blocks.append(
                "<div class='receipt-card'>"
                "<table class='receipt-top-table'><tr>"
                "<td class='receipt-icon-cell'><div class='receipt-icon'>&#128196;</div></td>"
                "<td class='receipt-meta-cell'>"
                f"<div class='receipt-title'>Receipt {index} - {entry.get('date', '-')}</div>"
                f"<div class='receipt-stats'><span>Solo Cups: {entry.get('daily_size_counts', {}).get('solo', 0)}</span>"
                f"<span>Large Cups: {entry.get('daily_size_counts', {}).get('large', 0)}</span>"
                f"<span>Total Orders: {total_orders}</span>"
                f"<span>Total Revenue: {money(total_revenue)}</span></div>"
                f"<div class='receipt-top-products'><b>Top Products:</b> {top_products_text}</div>"
                "</td></tr></table>"
                "<table class='report-table compact'>"
                "<thead><tr>"
                "<th>Time Slot</th><th>Milk Tea</th><th>Fruit Tea</th><th>Iced Coffee</th>"
                "<th>Milkshake</th><th>Cream Base</th><th>Total Orders</th><th>Revenue</th>"
                "</tr></thead><tbody>"
                f"{build_order_rows_table(rows)}"
                "</tbody></table></div>"
            )

        generated_label = QDateTime.currentDateTime().toString("MMMM d, yyyy h:mm AP")
        report_date = current.get("date", self.today_key())
        top_products_rows = build_top_products_rows(live["top_products"])
        inventory_rows_page_1 = build_inventory_table_rows(first_inventory_page)
        inventory_rows_page_2 = build_inventory_table_rows(second_inventory_page)
        summary_cards_html = "".join([
            summary_card("&#128722;", "Total Orders", str(live["total_orders"]), "Orders for the day", "amber"),
            summary_card("&#8369;", "Total Revenue", money(live["total_revenue"]), "Sales amount", "orange"),
            summary_card("&#128337;", "Most Active Slot", live["most_active_slot"], "Peak hour", "green"),
            summary_card("&#129380;", "Solo Cups Used", str(self.daily_size_counts.get("solo", 0)), "Packaging usage", "violet"),
            summary_card("&#129380;", "Large Cups Used", str(self.daily_size_counts.get("large", 0)), "Packaging usage", "blue"),
            summary_card("&#9888;", "Low Stock Items", str(live["low_stock_count"]), "Needs restocking", "red"),
        ])

        return f"""
        <html>
        <head>
        <style>
            @page {{
                size: A3 landscape;
                margin: 10mm;
            }}
            body {{
                font-family: Arial, sans-serif;
                color: #432616;
                margin: 0;
                background: #fcf7f1;
            }}
            .report-page {{
                width: 100%;
                padding: 2px 2px 0 2px;
            }}
            .page-break {{
                page-break-after: always;
            }}
            .brand-header {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 10px;
            }}
            .brand-header td {{
                vertical-align: middle;
                border: none;
                padding: 0;
            }}
            .brand-left {{
                width: 28%;
            }}
            .brand-center {{
                width: 62%;
                text-align: center;
            }}
            .brand-right {{
                width: 10%;
                text-align: right;
            }}
            .brand-badge {{
                display: inline-block;
                width: 54px;
                height: 54px;
                line-height: 54px;
                text-align: center;
                background: #6e3d20;
                color: #ffffff;
                border-radius: 27px;
                font-size: 24px;
                font-weight: 700;
                margin-right: 12px;
            }}
            .brand-stack {{
                display: inline-block;
                vertical-align: top;
                margin-top: 2px;
            }}
            .brand-name {{
                font-size: 28px;
                font-weight: 800;
                color: #4e2c1a;
                line-height: 1.05;
            }}
            .brand-sub {{
                font-size: 14px;
                font-weight: 700;
                color: #9b6a43;
                letter-spacing: 0.3px;
            }}
            .report-title {{
                font-size: 30px;
                font-weight: 900;
                color: #4a2a18;
                margin-bottom: 4px;
            }}
            .report-subtitle {{
                font-size: 15px;
                font-style: italic;
                color: #84644d;
            }}
            .header-icon {{
                display: inline-block;
                width: 44px;
                height: 44px;
                line-height: 44px;
                text-align: center;
                border-radius: 22px;
                background: #71706e;
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
            }}
            .meta-strip {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                margin: 10px 0 12px 0;
                border: 1px solid #ead5c4;
                border-radius: 12px;
                overflow: hidden;
            }}
            .meta-strip td {{
                border: none;
                padding: 11px 14px;
                background: #fff7ef;
                font-size: 14px;
                color: #6c4b36;
                font-weight: 700;
            }}
            .meta-strip td + td {{
                border-left: 1px solid #ead5c4;
            }}
            .section-bar {{
                background: #5a2f14;
                color: #ffffff;
                font-size: 18px;
                font-weight: 900;
                padding: 9px 14px;
                border-radius: 9px 9px 0 0;
                margin-top: 11px;
            }}
            .card-shell {{
                border: 1px solid #f0dccd;
                border-top: none;
                border-radius: 0 0 12px 12px;
                background: #fffaf5;
                padding: 13px;
            }}
            .summary-grid {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 11px;
                table-layout: fixed;
            }}
            .summary-grid td {{
                border: none;
                padding: 0;
                width: 16.66%;
            }}
            .summary-card {{
                border: 1px solid #eadbce;
                border-radius: 10px;
                min-height: 130px;
                text-align: center;
                padding: 15px 10px 13px 10px;
            }}
            .summary-card.amber {{ background: #fff8f0; }}
            .summary-card.orange {{ background: #fff4e8; }}
            .summary-card.green {{ background: #f5fbef; }}
            .summary-card.violet {{ background: #f7f3ff; }}
            .summary-card.blue {{ background: #f3f7ff; }}
            .summary-card.red {{ background: #fff3f0; }}
            .summary-icon {{
                font-size: 24px;
                margin-bottom: 6px;
            }}
            .summary-label {{
                font-size: 13px;
                font-weight: 800;
                color: #6e5543;
                margin-bottom: 6px;
            }}
            .summary-value {{
                font-size: 22px;
                font-weight: 900;
                color: #4a2917;
                margin-bottom: 6px;
            }}
            .summary-sub {{
                font-size: 11px;
                color: #8f7560;
            }}
            .report-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0;
                border: 1px solid #ecd9ca;
                border-top: none;
                border-radius: 0 0 12px 12px;
                overflow: hidden;
            }}
            .report-table th {{
                background: #6a391a;
                color: #ffffff;
                font-size: 14px;
                font-weight: 800;
                padding: 9px 10px;
                border: 1px solid rgba(255,255,255,0.10);
            }}
            .report-table td {{
                font-size: 13px;
                color: #4c2e1b;
                padding: 8px 10px;
                border: 1px solid #f1e2d6;
                text-align: center;
            }}
            .report-table td:first-child,
            .report-table th:first-child {{
                text-align: left;
            }}
            .report-table.compact td,
            .report-table.compact th {{
                font-size: 12px;
                padding: 8px 8px;
            }}
            .status-pill {{
                display: inline-block;
                min-width: 58px;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 800;
                text-align: center;
            }}
            .status-pill.good {{
                background: #eef8e8;
                color: #5f9347;
                border: 1px solid #cfe4c0;
            }}
            .status-pill.low {{
                background: #fff0ed;
                color: #d05e4d;
                border: 1px solid #f4c4bb;
            }}
            .status-pill.out {{
                background: #ffe7e3;
                color: #b83f31;
                border: 1px solid #efb5ab;
            }}
            .receipt-card {{
                border: 1px solid #f0dccd;
                border-radius: 12px;
                background: #fffaf5;
                padding: 14px;
                margin-top: 10px;
                page-break-inside: avoid;
            }}
            .receipt-top-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 10px;
            }}
            .receipt-top-table td {{
                border: none;
                padding: 0;
                vertical-align: top;
            }}
            .receipt-icon-cell {{
                width: 72px;
                padding-right: 14px;
            }}
            .receipt-icon {{
                display: inline-block;
                width: 58px;
                height: 58px;
                line-height: 58px;
                text-align: center;
                background: #fff3e7;
                color: #d08439;
                border: 1px solid #f0d8be;
                border-radius: 14px;
                font-size: 28px;
            }}
            .receipt-title {{
                font-size: 22px;
                font-weight: 900;
                color: #5a331d;
                margin-bottom: 6px;
            }}
            .receipt-stats span {{
                display: inline-block;
                margin-right: 18px;
                font-size: 13px;
                color: #6a4a35;
                font-weight: 700;
            }}
            .receipt-top-products {{
                font-size: 13px;
                color: #6a4a35;
                margin-top: 5px;
            }}
            .page-footer {{
                margin-top: 10px;
                border: 1px solid #ead5c4;
                border-radius: 10px;
                background: #fff7ef;
                padding: 10px 12px;
                font-size: 12px;
                color: #8a6d57;
            }}
            .footer-left {{
                float: left;
            }}
            .footer-right {{
                float: right;
                font-weight: 800;
                color: #6a4328;
            }}
            .clear {{
                clear: both;
            }}
            .empty-state {{
                text-align: center !important;
                color: #8a725f;
                padding: 18px !important;
            }}
        </style>
        </head>
        <body>
            <div class="report-page page-break">
                <table class="brand-header">
                    <tr>
                        <td class="brand-left">
                            <span class="brand-badge">&#9749;</span>
                            <span class="brand-stack">
                                <div class="brand-name">Best Brew</div>
                                <div class="brand-sub">ADMIN PORTAL</div>
                            </span>
                        </td>
                        <td class="brand-center">
                            <div class="report-title">Best Brew Admin Report</div>
                            <div class="report-subtitle">Whole-day operational summary and printable monitoring report</div>
                        </td>
                        <td class="brand-right">
                            <span class="header-icon">&#9398;</span>
                        </td>
                    </tr>
                </table>

                <table class="meta-strip">
                    <tr>
                        <td>&#128197; Generated: {generated_label}</td>
                        <td>&#128196; Current Report Date: {report_date}</td>
                        <td>&#128339; Store Hours: {self.store_hours_label()}</td>
                    </tr>
                </table>

                {section_bar(1, "CURRENT DAY SUMMARY")}
                <div class="card-shell">
                    <table class="summary-grid">
                        <tr>{summary_cards_html}</tr>
                    </table>
                </div>

                {section_bar(2, "TOP PRODUCTS")}
                <table class="report-table">
                    <thead>
                        <tr><th>Product</th><th>Category</th><th>Units Sold</th><th>Revenue</th></tr>
                    </thead>
                    <tbody>{top_products_rows}</tbody>
                </table>

                {section_bar(3, "INVENTORY SNAPSHOT")}
                <table class="report-table">
                    <thead>
                        <tr><th>Item</th><th>Category</th><th>Current Stock</th><th>Reorder Level</th><th>Status</th></tr>
                    </thead>
                    <tbody>{inventory_rows_page_1}</tbody>
                </table>

                <div class="page-footer">
                    <div class="footer-left">&#9432; Inventory Snapshot continues on page 2</div>
                    <div class="footer-right">Page 1 of 2</div>
                    <div class="clear"></div>
                </div>
            </div>

            <div class="report-page">
                <table class="brand-header">
                    <tr>
                        <td class="brand-left">
                            <span class="brand-badge">&#9749;</span>
                            <span class="brand-stack">
                                <div class="brand-name">Best Brew</div>
                                <div class="brand-sub">ADMIN PORTAL</div>
                            </span>
                        </td>
                        <td class="brand-center">
                            <div class="report-title">Best Brew Admin Report</div>
                            <div class="report-subtitle">Whole-day operational summary and printable monitoring report</div>
                        </td>
                        <td class="brand-right">
                            <span class="header-icon">&#9398;</span>
                        </td>
                    </tr>
                </table>

                {section_bar(3, "INVENTORY SNAPSHOT", continued=True)}
                <table class="report-table">
                    <thead>
                        <tr><th>Item</th><th>Category</th><th>Current Stock</th><th>Reorder Level</th><th>Status</th></tr>
                    </thead>
                    <tbody>{inventory_rows_page_2}</tbody>
                </table>

                {section_bar(4, "SAVED ORDER SUMMARY")}
                {"".join(receipt_blocks) or "<div class='receipt-card'><div class='empty-state'>No saved receipts yet.</div></div>"}

                <div class="page-footer">
                    <div class="footer-left">&#9432; Inventory Snapshot continued from page 1</div>
                    <div class="footer-right">Page 2 of 2</div>
                    <div class="clear"></div>
                </div>
            </div>
        </body>
        </html>
        """

    def build_export_report_html(self):
        return self._build_export_report_html_styled()

    def _build_export_report_html_legacy(self):
        self.persist_order_summary_progress()
        live = self.collect_live_system_data()
        state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        current = state.get("current") or self.build_current_order_summary_snapshot()

        def money(value):
            return f"PHP {int(value):,}"

        def section_bar(title):
            return f"<div class='section-bar'>{title}</div>"

        def status_badge(status):
            normalized = str(status or "").strip().lower()
            if normalized == "good":
                badge_class = "good"
            elif normalized == "low":
                badge_class = "low"
            else:
                badge_class = "out"
            return f"<span class='status-pill {badge_class}'>{status}</span>"

        def build_order_rows_table(rows):
            body = []
            for row in rows:
                if len(row) >= 8:
                    body.append(
                        "<tr>"
                        f"<td>{row[0]}</td>"
                        f"<td>{row[1]}</td>"
                        f"<td>{row[2]}</td>"
                        f"<td>{row[3]}</td>"
                        f"<td>{row[4]}</td>"
                        f"<td>{row[5]}</td>"
                        f"<td>{row[6]}</td>"
                        f"<td>{money(self.safe_int(row[7]))}</td>"
                        "</tr>"
                    )
            return "".join(body) or "<tr><td colspan='8' class='empty-state'>No order summary recorded.</td></tr>"

        def build_inventory_table_rows(items):
            rows = []
            for item in items:
                rows.append(
                    "<tr>"
                    f"<td>{item.get('name', '-')}</td>"
                    f"<td>{item.get('category', '-')}</td>"
                    f"<td>{item.get('stock', '-')}</td>"
                    f"<td>{item.get('reorder', '-')}</td>"
                    f"<td>{status_badge(item.get('status', '-'))}</td>"
                    "</tr>"
                )
            return "".join(rows) or "<tr><td colspan='5' class='empty-state'>No inventory data available.</td></tr>"

        def build_top_products_rows(products):
            rows = []
            for product in products[:10]:
                rows.append(
                    "<tr>"
                    f"<td>{product.get('name', '-')}</td>"
                    f"<td>{product.get('subtitle', '-')}</td>"
                    f"<td>{product.get('units', 0)}</td>"
                    f"<td>{money(product.get('revenue', 0))}</td>"
                    "</tr>"
                )
            return "".join(rows) or "<tr><td colspan='4' class='empty-state'>No product sales yet.</td></tr>"

        def summary_row(label, value, note):
            return (
                "<tr>"
                f"<td class='summary-label-cell'>{label}</td>"
                f"<td class='summary-value-cell'>{value}</td>"
                f"<td class='summary-note-cell'>{note}</td>"
                "</tr>"
            )

        def build_product_type_rows(rows):
            totals = {
                "Milk Tea": 0,
                "Fruit Tea": 0,
                "Iced Coffee": 0,
                "Milkshake": 0,
                "Cream Base": 0,
            }
            for row in rows:
                if len(row) >= 8:
                    totals["Milk Tea"] += self.safe_int(row[1])
                    totals["Fruit Tea"] += self.safe_int(row[2])
                    totals["Iced Coffee"] += self.safe_int(row[3])
                    totals["Milkshake"] += self.safe_int(row[4])
                    totals["Cream Base"] += self.safe_int(row[5])

            body = []
            for label, count in totals.items():
                body.append(
                    "<tr>"
                    f"<td>{label}</td>"
                    f"<td>{count}</td>"
                    "</tr>"
                )
            return "".join(body)

        def build_cup_usage_rows(size_counts):
            solo = self.safe_int(size_counts.get("solo", 0))
            large = self.safe_int(size_counts.get("large", 0))
            return (
                "<tr><td>Solo Cups</td><td>{}</td></tr>"
                "<tr><td>Large Cups</td><td>{}</td></tr>"
            ).format(solo, large)

        def build_inventory_deduction_rows(entries, inventory_items):
            product_lookup = {
                str(product.get("name", "")).strip(): product
                for product in getattr(self, "products", [])
            }
            inventory_lookup = {
                item.get("id"): item
                for item in inventory_items
                if item.get("id") is not None
            }
            deductions = {}

            for entry in entries or []:
                product_name = str(entry.get("product_name", "")).strip()
                product = product_lookup.get(product_name, {
                    "name": product_name or "Product",
                    "category": str(entry.get("category", "")).strip() or "Product",
                })
                order_config = {
                    "size": entry.get("size", "Solo"),
                    "quantity": self.safe_int(entry.get("quantity", 1)) or 1,
                    "addons": list(entry.get("addons", []) or []),
                }
                plan = self.inventory_consumption_plan(product, order_config)
                for inventory_id, amount in plan.items():
                    item = inventory_lookup.get(inventory_id)
                    item_name = item.get("name", "Inventory Item") if item else "Inventory Item"
                    deductions[item_name] = deductions.get(item_name, 0) + amount

            if not deductions:
                return "<tr><td colspan='2' class='empty-state'>No tracked inventory deductions for this date.</td></tr>"

            rows = []
            for item_name, amount in sorted(deductions.items(), key=lambda pair: pair[0].lower()):
                rows.append(
                    "<tr>"
                    f"<td>{item_name}</td>"
                    f"<td>{amount}</td>"
                    "</tr>"
                )
            return "".join(rows)

        generated_label = QDateTime.currentDateTime().toString("MMMM d, yyyy h:mm AP")
        report_date = current.get("date", self.today_key())
        current_rows = current.get("order_rows", [])
        current_entries = current.get("order_entries", [])
        inventory_items = list(getattr(self, "inventory_items", []))
        top_products_rows = build_top_products_rows(live["top_products"])
        product_type_rows = build_product_type_rows(current_rows)
        cup_usage_rows = build_cup_usage_rows(current.get("daily_size_counts", {}))
        inventory_deduction_rows = build_inventory_deduction_rows(current_entries, inventory_items)
        summary_cards_html = "".join([
            summary_row("Order Summary Date", report_date, "Daily report basis"),
            summary_row("Whole Day Revenue", money(live["total_revenue"]), "Total kita sa buong araw"),
            summary_row("Total Orders", str(live["total_orders"]), "Total items/orders logged"),
            summary_row("Most Active Slot", live["most_active_slot"], "Pinaka-busy na oras"),
        ])

        return f"""
        <html>
        <head>
        <style>
            @page {{
                size: A3 landscape;
                margin: 12mm;
            }}
            body {{
                font-family: Arial, sans-serif;
                color: #111111;
                margin: 0;
                background: #ffffff;
            }}
            .report-page {{
                width: 100%;
            }}
            .report-header {{
                border-bottom: 1px solid #999999;
                padding-bottom: 8px;
                margin-bottom: 12px;
            }}
            .brand-name {{
                font-size: 16px;
                font-weight: 800;
                color: #111111;
                margin-bottom: 2px;
            }}
            .brand-sub {{
                font-size: 11px;
                font-weight: 700;
                color: #444444;
            }}
            .report-title {{
                font-size: 20px;
                font-weight: 900;
                color: #111111;
                margin: 8px 0 2px 0;
            }}
            .report-subtitle {{
                font-size: 12px;
                color: #444444;
            }}
            .meta-strip {{
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0 14px 0;
                border: 1px solid #999999;
            }}
            .meta-strip td {{
                padding: 8px 10px;
                background: #ffffff;
                font-size: 12px;
                color: #111111;
                font-weight: 700;
                border: 1px solid #999999;
            }}
            .section-bar {{
                background: transparent;
                color: #111111;
                font-size: 16px;
                font-weight: 900;
                padding: 0;
                border: none;
                margin-top: 14px;
                margin-bottom: 6px;
            }}
            .summary-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0 0 10px 0;
                border: 1px solid #999999;
            }}
            .summary-table th {{
                background: #ffffff;
                color: #111111;
                font-size: 14px;
                font-weight: 900;
                padding: 9px 10px;
                border: 1px solid #999999;
                text-align: left;
            }}
            .summary-table td {{
                font-size: 14px;
                padding: 9px 10px;
                border: 1px solid #999999;
            }}
            .summary-label-cell {{
                width: 28%;
                font-weight: 800;
                color: #111111;
            }}
            .summary-value-cell {{
                width: 27%;
                font-weight: 900;
                color: #111111;
            }}
            .summary-note-cell {{
                color: #333333;
            }}
            .report-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0 0 12px 0;
                border: 1px solid #999999;
            }}
            .report-table th {{
                background: #ffffff;
                color: #111111;
                font-size: 15px;
                font-weight: 900;
                padding: 10px 8px;
                border: 1px solid #999999;
            }}
            .report-table td {{
                font-size: 14px;
                color: #111111;
                padding: 10px 8px;
                border: 1px solid #999999;
                text-align: center;
                vertical-align: top;
            }}
            .report-table td:first-child,
            .report-table th:first-child {{
                text-align: left;
            }}
            .report-table.compact th {{
                font-size: 14px;
                padding: 9px 8px;
            }}
            .report-table.compact td {{
                font-size: 13px;
                padding: 8px 8px;
            }}
            .empty-state {{
                text-align: center !important;
                color: #444444;
                padding: 14px !important;
            }}
        </style>
        </head>
        <body>
            <div class="report-page">
                <div class="report-header">
                    <div class="brand-name">Best Brew</div>
                    <div class="brand-sub">ADMIN PORTAL</div>
                    <div class="report-title">Daily Admin Report</div>
                    <div class="report-subtitle">Simple and readable summary for day-to-day store monitoring</div>
                </div>

                <table class="meta-strip">
                    <tr>
                        <td>Generated: {generated_label}</td>
                        <td>Report Date: {report_date}</td>
                        <td>Store Hours: {self.store_hours_label()}</td>
                    </tr>
                </table>

                {section_bar("CURRENT DAY SUMMARY")}
                <table class="summary-table">
                    <thead>
                        <tr><th>Metric</th><th>Value</th><th>Notes</th></tr>
                    </thead>
                    <tbody>{summary_cards_html}</tbody>
                </table>

                {section_bar("CUPS USED")}
                <table class="report-table">
                    <thead>
                        <tr><th>Cup Size</th><th>Quantity Used</th></tr>
                    </thead>
                    <tbody>{cup_usage_rows}</tbody>
                </table>

                {section_bar("PRODUCT TYPES SOLD")}
                <table class="report-table">
                    <thead>
                        <tr><th>Product Type</th><th>Quantity Sold</th></tr>
                    </thead>
                    <tbody>{product_type_rows}</tbody>
                </table>

                {section_bar("PRODUCTS SOLD")}
                <table class="report-table">
                    <thead>
                        <tr><th>Product</th><th>Category</th><th>Units Sold</th><th>Revenue</th></tr>
                    </thead>
                    <tbody>{top_products_rows}</tbody>
                </table>

                {section_bar("INVENTORY DEDUCTIONS")}
                <table class="report-table">
                    <thead>
                        <tr><th>Inventory Item</th><th>Quantity Deducted</th></tr>
                    </thead>
                    <tbody>{inventory_deduction_rows}</tbody>
                </table>
            </div>
        </body>
        </html>
        """

    def build_export_report_document(self, page_size=None):
        document = QTextDocument()
        document.setHtml(self.build_export_report_html())
        if page_size is not None:
            document.setPageSize(page_size)
        return document

    def render_export_report_pages(self, page_width=1754, page_height=1240):
        document = self.build_export_report_document(QSizeF(page_width, page_height))
        page_count = max(1, document.pageCount())
        pages = []

        for page_index in range(page_count):
            image = QImage(page_width, page_height, QImage.Format_ARGB32)
            image.fill(QColor("#fffaf5"))

            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            context = QAbstractTextDocumentLayout.PaintContext()
            context.clip = QRectF(0, page_index * page_height, page_width, page_height)
            painter.translate(0, -page_index * page_height)
            document.documentLayout().draw(painter, context)
            painter.end()
            pages.append(image)

        return pages

    def export_admin_pdf_report(self, show_notification=True):
        export_dir = os.path.join(PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_path = build_unique_export_path(
            export_dir,
            "bestbrew_admin_report",
            self.active_summary_date_key(),
            ".pdf",
        )

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setPageSize(QPageSize(QPageSize.A3))
        printer.setPageOrientation(QPageLayout.Landscape)

        document = self.build_export_report_document()
        document.print_(printer)

        if show_notification:
            self.show_notification("Export Complete", f"PDF report exported successfully:\n{export_path}", "success", 3200)
        return export_path

    def export_admin_png_report(self, show_notification=True):
        export_dir = os.path.join(PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        pages = self.render_export_report_pages()
        export_paths = []

        for page_index, image in enumerate(pages):
            export_path = build_unique_export_path(
                export_dir,
                f"bestbrew_admin_report_page{page_index + 1}",
                self.active_summary_date_key(),
                ".png",
            )
            image.save(export_path, "PNG")
            export_paths.append(export_path)

        if show_notification and export_paths:
            self.show_notification(
                "Export Complete",
                "PNG report exported successfully:\n" + "\n".join(export_paths),
                "success",
                3600,
            )
        return export_paths

    def export_admin_word_image_report(self, show_notification=True):
        export_dir = os.path.join(PROJECT_ROOT, "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_path = build_unique_export_path(
            export_dir,
            "bestbrew_admin_report",
            self.active_summary_date_key(),
            ".doc",
        )

        generated_label = QDateTime.currentDateTime().toString("MMMM d, yyyy h:mm AP")
        pages = self.render_export_report_pages()
        image_blocks = []

        for page_number, image in enumerate(pages, start=1):
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            image.save(buffer, "PNG")
            buffer.close()
            encoded = base64.b64encode(bytes(byte_array)).decode("ascii")
            image_blocks.append(
                "<div class='page-wrap'>"
                f"<div class='page-label'>Report Page {page_number}</div>"
                f"<img src='data:image/png;base64,{encoded}' alt='Best Brew Report Page {page_number}' />"
                "</div>"
            )

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Best Brew Admin Report</title>
<style>
body {{
    font-family: Arial, sans-serif;
    background: #f7efe6;
    margin: 0;
    padding: 24px;
    color: #4a2a18;
}}
.doc-shell {{
    max-width: 1220px;
    margin: 0 auto;
}}
.doc-title {{
    font-size: 26px;
    font-weight: 800;
    margin-bottom: 4px;
}}
.doc-subtitle {{
    font-size: 13px;
    color: #7a5a45;
    margin-bottom: 8px;
}}
.doc-meta {{
    font-size: 12px;
    color: #7a5a45;
    margin-bottom: 18px;
}}
.page-wrap {{
    background: #fffaf5;
    border: 1px solid #ead5c4;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 18px;
}}
.page-label {{
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 10px;
    color: #6a391a;
}}
img {{
    width: 100%;
    height: auto;
    display: block;
    border-radius: 12px;
}}
</style>
</head>
<body>
    <div class="doc-shell">
        <div class="doc-title">Best Brew Admin Report</div>
        <div class="doc-subtitle">Embedded image report for Word document viewing</div>
        <div class="doc-meta">Generated: {generated_label} | Report Date: {self.active_summary_date_key()} | Pages: {len(pages)}</div>
        {''.join(image_blocks)}
    </div>
</body>
</html>
"""

        with open(export_path, "w", encoding="utf-8") as fh:
            fh.write(html)

        if show_notification:
            self.show_notification("Export Complete", f"Word report exported successfully:\n{export_path}", "success", 3600)
        return export_path

    def clear_layout_widgets(self, layout, keep=0):
        while layout.count() > keep:
            item = layout.takeAt(keep)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self.clear_layout_widgets(child_layout, 0)

    def iter_order_summary_rows(self):
        if hasattr(self, "orders_table"):
            for row in range(self.order_data_row_count()):
                yield {
                    "slot": self.orders_table.item(row, 0).text() if self.orders_table.item(row, 0) else "-",
                    "milk": self.safe_int(self.orders_table.item(row, 1).text() if self.orders_table.item(row, 1) else 0),
                    "fruit": self.safe_int(self.orders_table.item(row, 2).text() if self.orders_table.item(row, 2) else 0),
                    "iced_coffee": self.safe_int(self.orders_table.item(row, 3).text() if self.orders_table.item(row, 3) else 0),
                    "milkshake": self.safe_int(self.orders_table.item(row, 4).text() if self.orders_table.item(row, 4) else 0),
                    "cream_base": self.safe_int(self.orders_table.item(row, 5).text() if self.orders_table.item(row, 5) else 0),
                    "total_orders": self.safe_int(self.orders_table.item(row, 6).text() if self.orders_table.item(row, 6) else 0),
                    "revenue": self.safe_int(self.orders_table.item(row, 7).text() if self.orders_table.item(row, 7) else 0),
                }
            return

        for row in self.order_rows:
            yield {
                "slot": row[0] if len(row) > 0 else "-",
                "milk": self.safe_int(row[1] if len(row) > 1 else 0),
                "fruit": self.safe_int(row[2] if len(row) > 2 else 0),
                "iced_coffee": self.safe_int(row[3] if len(row) > 3 else 0),
                "milkshake": self.safe_int(row[4] if len(row) > 4 else 0),
                "cream_base": self.safe_int(row[5] if len(row) > 5 else 0),
                "total_orders": self.safe_int(row[6] if len(row) > 6 else 0),
                "revenue": self.safe_int(row[7] if len(row) > 7 else 0),
            }

    def live_low_stock_items(self):
        items = []
        for item in getattr(self, "inventory_items", []):
            if str(item.get("status", "")).strip().lower() in {"low", "out"}:
                normalized_name = str(item.get("name", "")).strip()
                icon_text = str(item.get("icon", "")).strip() or "".join(word[:1] for word in normalized_name.split()[:2]).upper() or "IT"
                items.append({
                    "name": normalized_name or "Inventory Item",
                    "stock": item.get("stock", "-"),
                    "reorder": item.get("reorder", "-"),
                    "accent": item.get("accent", "#b77746"),
                    "emoji": icon_text,
                    "status": item.get("status", "Low"),
                    "id": item.get("id"),
                })
        return items

    def live_top_products_data(self, limit=5):
        product_lookup = {str(product.get("name", "")).strip(): product for product in getattr(self, "products", [])}
        ranked = sorted(self.daily_product_sales.items(), key=lambda item: (-item[1], item[0]))
        result = []
        for name, units in ranked[:limit]:
            product = product_lookup.get(name, {})
            price_value = self.price_value_from_text(product.get("price_text", "0"))
            category = str(product.get("category", "Product")).strip() or "Product"
            result.append({
                "name": name,
                "subtitle": category,
                "price": f"\u20b1{price_value * units:,}",
                "sold": f"{units} sold",
                "image": product.get("image", ""),
                "stock": product.get("stock", "-"),
                "accent": product.get("accent", "#b77746"),
                "reorder": product.get("reorder", "-"),
                "emoji": product.get("emoji", "●"),
                "units": units,
                "revenue": price_value * units,
                "status": "Active",
            })
        return result

    def normalize_order_status(self, status):
        return self.controller.normalize_order_status(status)

    def current_order_status_counts(self):
        return self.controller.current_order_status_counts(getattr(self, "order_entries", []))

    def build_order_entry(self, product, order_config, slot_label, order_total):
        return self.controller.build_order_entry(
            product,
            order_config,
            slot_label,
            order_total,
            getattr(self, "order_entries", []),
        )

    def update_order_entry_status(self, entry_id, status):
        updated = False
        db_order_id = None
        for entry in getattr(self, "order_entries", []):
            if str(entry.get("id")) == str(entry_id):
                entry["status"] = self.normalize_order_status(status)
                db_order_id = entry.get("db_order_id")
                updated = True
                break
        if not updated:
            return

        try:
            if db_order_id:
                database.update_order_record_status(db_order_id, self.normalize_order_status(status))
        except Exception as e:
            self.show_notification("Status Error", f"Could not update order status in database:\n{e}", "error", 3400)
            return

        self.add_recent_activity("#7d5ac7", "•", f"Order {entry_id} marked as {self.normalize_order_status(status)}")
        self.refresh_order_entries_table()
        self.persist_order_summary_progress()
        self.refresh_connected_views()

    def cancel_order_entry(self, entry_id):
        entry_to_remove = None
        for entry in getattr(self, "order_entries", []):
            if str(entry.get("id")) == str(entry_id):
                entry_to_remove = dict(entry or {})
                break
        if not entry_to_remove:
            return

        dialog = ConfirmActionDialog(
            self,
            title="Cancel Order",
            message=f"Remove order {entry_id} from today's orders?",
            confirm_text="Cancel Order",
            cancel_text="Keep",
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            product_stub = {
                "name": entry_to_remove.get("product_name", ""),
                "category": entry_to_remove.get("category", ""),
            }
            order_config = {
                "size": entry_to_remove.get("size", "Solo"),
                "quantity": entry_to_remove.get("quantity", 1),
                "addons": list(entry_to_remove.get("addons", []) or []),
            }
            plan = self.inventory_consumption_plan(product_stub, order_config)
            for inventory_id, amount in plan.items():
                self.controller.restock_inventory_item(inventory_id, amount)

            remaining_entries = [
                dict(entry or {})
                for entry in getattr(self, "order_entries", [])
                if str(entry.get("id")) != str(entry_id)
            ]
            db_order_id = entry_to_remove.get("db_order_id")
            if db_order_id:
                database.delete_order_record(db_order_id)
            rebuilt_snapshot = self.rebuild_snapshot_from_entries(self.active_summary_date_key(), remaining_entries)
            self.apply_order_summary_snapshot(rebuilt_snapshot)
            self.sync_orders_table_from_order_rows()
            self.inventory_items = self.load_inventory_from_database()
            self.refresh_inventory_page_if_visible()
            self.refresh_order_entries_table()
            self.refresh_order_summary()
            self.persist_order_summary_progress()
            self.refresh_connected_views()
            self.show_notification("Order Cancelled", f"Order {entry_id} was removed successfully.", "success", 2600)
        except Exception as e:
            self.show_notification("Cancel Error", f"Could not cancel the order:\n{e}", "error", 3400)

    def snapshot_total_revenue(self, snapshot):
        rows = snapshot.get("order_rows", []) if isinstance(snapshot, dict) else []
        return sum(self.safe_int(row[7]) for row in rows if isinstance(row, list) and len(row) > 7)

    def revenue_chart_series(self, days=7):
        self.rollover_order_summary_if_needed()
        state = getattr(self, "order_summary_state", None) or self.summary_history_template()
        snapshots = []

        current = state.get("current")
        if isinstance(current, dict):
            snapshots.append(current)

        for entry in state.get("history", []):
            if isinstance(entry, dict):
                snapshots.append(entry)

        revenue_by_date = {}
        for snapshot in snapshots:
            snapshot_date = str(snapshot.get("date", "")).strip()
            if not snapshot_date or snapshot_date in revenue_by_date:
                continue
            revenue_by_date[snapshot_date] = self.snapshot_total_revenue(snapshot)

        today = QDateTime.currentDateTime().date()
        labels = []
        values = []
        for offset in range(-(days - 1), 1):
            target_date = today.addDays(offset)
            iso_key = target_date.toString("yyyy-MM-dd")
            labels.append(target_date.toString("MMM d"))
            values.append(revenue_by_date.get(iso_key, 0))

        return labels, values

    def collect_live_system_data(self):
        self.rollover_order_summary_if_needed()
        rows = list(self.iter_order_summary_rows())
        total_logged_orders = sum(row["total_orders"] for row in rows)
        total_revenue = sum(row["revenue"] for row in rows)
        most_active_slot = "-"
        highest_orders = -1

        for row in rows:
            if row["total_orders"] > highest_orders:
                highest_orders = row["total_orders"]
                most_active_slot = row["slot"]

        low_stock_items = self.live_low_stock_items()
        top_products = self.live_top_products_data(limit=6)
        status_counts = self.current_order_status_counts()
        total_orders = sum(status_counts.values())
        today_label = QDateTime.currentDateTime().toString("MMM d")
        revenue_labels, revenue_values = self.revenue_chart_series(days=7)
        donut_values = [
            status_counts["Completed"],
            status_counts["Processing"],
            status_counts["Pending"],
        ]

        if sum(donut_values) <= 0:
            donut_values = [1, 0, 0]

        def percent(count):
            return f"{round((count / total_orders) * 100)}%" if total_orders else "0%"

        return {
            "total_products": len(getattr(self, "products", [])),
            "total_orders": total_orders,
            "total_logged_orders": total_logged_orders,
            "total_revenue": total_revenue,
            "low_stock_count": len(low_stock_items),
            "low_stock_items": low_stock_items,
            "most_active_slot": most_active_slot,
            "total_slots": len(rows),
            "top_products": top_products,
            "top_product_text": f"{top_products[0]['name']} ({top_products[0]['units']})" if top_products else "-",
            "revenue_labels": revenue_labels,
            "revenue_values": revenue_values,
            "analytics_status": [
                ("#76b255", "Completed", status_counts["Completed"], percent(status_counts["Completed"])),
                ("#f0aa2b", "Processing", status_counts["Processing"], percent(status_counts["Processing"])),
                ("#a87543", "Pending", status_counts["Pending"], percent(status_counts["Pending"])),
            ],
            "donut_values": donut_values,
            "order_status_counts": status_counts,
            "today_label": today_label,
        }

    def rebuild_stack_page(self, index, builder_name):
        if not hasattr(self, "stack") or self.stack.count() <= index:
            return
        current_index = self.stack.currentIndex()
        self.ensure_stack_page_loaded(index, force_rebuild=True)
        self.stack.setCurrentIndex(current_index)
        self._apply_nav_button_state(current_index)

    def mark_page_dirty(self, index, builder_name):
        self._dirty_page_builders[index] = builder_name

    def _apply_nav_button_state(self, index):
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setObjectName("navButtonActive")
            else:
                btn.setObjectName("navButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _schedule_page_refresh(self, index, delay_ms=0):
        if index in self._scheduled_page_refreshes:
            return
        if index not in self._dirty_page_builders:
            return

        self._scheduled_page_refreshes.add(index)

        def run_refresh():
            self._scheduled_page_refreshes.discard(index)
            builder_name = self._dirty_page_builders.get(index)
            if not builder_name or not hasattr(self, "stack") or self.stack.count() <= index:
                return
            if self.stack.currentIndex() != index:
                return
            self._dirty_page_builders.pop(index, None)
            self.rebuild_stack_page(index, builder_name)

        QTimer.singleShot(delay_ms, run_refresh)

    def refresh_connected_views(self, include_products=False):
        dashboard_index = self.page_index_by_builder_name("page_dashboard_v2")
        analytics_index = self.page_index_by_builder_name("page_analytics")
        products_index = self.page_index_by_builder_name("page_products")
        receipts_index = self.page_index_by_builder_name("page_cashier_receipts")
        cashier_orders_index = self.page_index_by_builder_name("page_cashier_orders")
        if dashboard_index is not None:
            self.mark_page_dirty(dashboard_index, "page_dashboard_v2")
        if analytics_index is not None:
            self.mark_page_dirty(analytics_index, "page_analytics")
        if include_products and products_index is not None:
            self.mark_page_dirty(products_index, "page_products")
        if receipts_index is not None:
            self.mark_page_dirty(receipts_index, "page_cashier_receipts")
            if hasattr(self, "stack") and self.stack.currentIndex() == receipts_index:
                self._schedule_page_refresh(receipts_index, 0)
        if cashier_orders_index is not None:
            self.mark_page_dirty(cashier_orders_index, "page_cashier_orders")
            if hasattr(self, "stack") and self.stack.currentIndex() == cashier_orders_index:
                self._schedule_page_refresh(cashier_orders_index, 0)

    def refresh_inventory_page_if_visible(self):
        inventory_index = self.page_index_by_builder_name("page_inventory")
        if inventory_index is None or not hasattr(self, "stack") or self.stack.count() <= inventory_index:
            return
        self.mark_page_dirty(inventory_index, "page_inventory")
        if self.stack.currentIndex() == inventory_index:
            self._schedule_page_refresh(inventory_index, 0)

    def refresh_users_page_if_visible(self):
        users_index = self.page_index_by_builder_name("page_users")
        if users_index is None or not hasattr(self, "stack") or self.stack.count() <= users_index:
            return
        self.mark_page_dirty(users_index, "page_users")
        if self.stack.currentIndex() == users_index:
            self._schedule_page_refresh(users_index, 0)

    def add_recent_activity(self, color, icon_text, title, timestamp="Just now", activity_type=None, product_name=None, image_path=None):
        self.recent_activities.append({
            "color": color,
            "icon": icon_text,
            "title": title,
            "timestamp": timestamp,
            "activity_type": activity_type or "generic",
            "product_name": product_name or "",
            "image_path": image_path or "",
        })
        self.recent_activities = self.recent_activities[-12:]

    def load_inventory_from_database(self):
        try:
            rows = self.controller.get_inventory_items()
            return self.controller.map_inventory_items(rows)

        except Exception as e:
            print(f"Cannot load inventory: {e}")
            return self.fallback_inventory_data()

    def load_users_from_database(self):
        try:
            return self.controller.get_users()
        except Exception as e:
            print(f"Cannot load users: {e}")
            return []

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.build_sidebar_v2())
        root.addWidget(self.build_main_stack(), 1)

    def build_sidebar_v2(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220 if self.is_cashier_role() else 300)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14 if self.is_cashier_role() else 18, 24 if self.is_cashier_role() else 28, 14 if self.is_cashier_role() else 18, 18 if self.is_cashier_role() else 22)
        layout.setSpacing(14 if self.is_cashier_role() else 18)

        if self.is_cashier_role():
            divider = QFrame()
            divider.setObjectName("sidebarDivider")
            layout.addWidget(divider)

            profile_card = QFrame()
            profile_card.setObjectName("cashierProfileCard")
            profile_layout = QVBoxLayout(profile_card)
            profile_layout.setContentsMargins(12, 12, 12, 12)
            profile_layout.setSpacing(8)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(10)
            avatar = QLabel("BB")
            avatar.setObjectName("cashierAvatar")
            avatar.setAlignment(Qt.AlignCenter)

            details = QVBoxLayout()
            details.setContentsMargins(0, 0, 0, 0)
            details.setSpacing(1)
            name_lbl = QLabel("Best Brew")
            name_lbl.setObjectName("cashierName")
            role_lbl = QLabel("Cashier Portal")
            role_lbl.setObjectName("cashierRole")
            status_lbl = QLabel("Online")
            status_lbl.setObjectName("cashierStatus")
            status_lbl.setText("Online")
            details.addWidget(name_lbl)
            details.addWidget(role_lbl)
            details.addWidget(status_lbl, 0, Qt.AlignLeft)

            top_row.addWidget(avatar)
            top_row.addLayout(details, 1)
            profile_layout.addLayout(top_row)

            status_lbl = QLabel("● Online")
            layout.addWidget(profile_card)
            layout.addSpacing(10)
        else:
            brand_badge = QFrame()
            brand_badge.setObjectName("brandBadge")
            brand_row = QHBoxLayout(brand_badge)
            brand_row.setContentsMargins(4, 0, 4, 0)
            brand_row.setSpacing(12)

            brand_icon = QLabel("BB")
            brand_icon.setObjectName("brandIcon")
            brand_icon.setAlignment(Qt.AlignCenter)

            brand_col = QVBoxLayout()
            brand_col.setContentsMargins(0, 0, 0, 0)
            brand_col.setSpacing(2)
            brand_title = QLabel("Best Brew")
            brand_title.setObjectName("brandTitle")
            brand_sub = QLabel(self.dashboard_portal_label())
            brand_sub.setObjectName("brandSub")
            brand_col.addWidget(brand_title)
            brand_col.addWidget(brand_sub)

            brand_row.addWidget(brand_icon)
            brand_row.addLayout(brand_col)
            brand_row.addStretch()
            layout.addWidget(brand_badge)
            layout.addSpacing(20)

        for index, (text, icon, _) in enumerate(self.navigation_pages()):
            btn = QPushButton(text)
            btn.setIcon(icon)
            btn.setIconSize(QSize(18 if self.is_cashier_role() else 20, 18 if self.is_cashier_role() else 20))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setLayoutDirection(Qt.LeftToRight)
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        if not self.is_cashier_role():
            decor = QLabel("o o o")
            decor.setObjectName("sidebarDecor")
            decor.setAlignment(Qt.AlignRight)
            layout.addWidget(decor)

            divider = QFrame()
            divider.setObjectName("sidebarDivider")
            layout.addWidget(divider)

        exit_btn = QPushButton("Logout" if self.is_cashier_role() else "Exit to Home")
        exit_btn.setObjectName("exitBtn")
        exit_btn.setIcon(self.nav_icon("back.svg"))
        exit_btn.setIconSize(QSize(18, 18))
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.clicked.connect(self.exit_to_home)
        layout.addWidget(exit_btn)

        return sidebar

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220 if self.is_cashier_role() else 300)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14 if self.is_cashier_role() else 18, 24 if self.is_cashier_role() else 28, 14 if self.is_cashier_role() else 18, 18 if self.is_cashier_role() else 22)
        layout.setSpacing(14 if self.is_cashier_role() else 18)

        brand_badge = QFrame()
        brand_badge.setObjectName("brandBadge")
        brand_row = QHBoxLayout(brand_badge)
        brand_row.setContentsMargins(4, 0, 4, 0)
        brand_row.setSpacing(12)

        brand_icon = QLabel("BB")
        brand_icon.setObjectName("brandIcon")
        brand_icon.setAlignment(Qt.AlignCenter)

        brand_col = QVBoxLayout()
        brand_col.setContentsMargins(0, 0, 0, 0)
        brand_col.setSpacing(2)
        brand_title = QLabel("Best Brew")
        brand_title.setObjectName("brandTitle")
        brand_sub = QLabel(self.dashboard_portal_label())
        brand_sub.setObjectName("brandSub")

        brand_col.addWidget(brand_title)
        brand_col.addWidget(brand_sub)

        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_col)
        brand_row.addStretch()

        if self.is_cashier_role():
            brand_badge.hide()
        else:
            layout.addWidget(brand_badge)
            layout.addSpacing(20)

        for index, (text, icon, _) in enumerate(self.navigation_pages()):
            btn = QPushButton(text)
            btn.setIcon(icon)
            btn.setIconSize(QSize(18 if self.is_cashier_role() else 20, 18 if self.is_cashier_role() else 20))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setLayoutDirection(Qt.LeftToRight)
            btn.clicked.connect(lambda checked, i=index: self.switch_page(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        if self.is_cashier_role():
            divider = QFrame()
            divider.setObjectName("sidebarDivider")
            layout.addWidget(divider)

            profile_card = QFrame()
            profile_card.setObjectName("cashierProfileCard")
            profile_layout = QVBoxLayout(profile_card)
            profile_layout.setContentsMargins(12, 12, 12, 12)
            profile_layout.setSpacing(8)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(10)
            avatar = QLabel(self.current_user_initials())
            avatar.setObjectName("cashierAvatar")
            avatar.setAlignment(Qt.AlignCenter)
            self.user_avatar_labels.append(avatar)

            details = QVBoxLayout()
            details.setContentsMargins(0, 0, 0, 0)
            details.setSpacing(1)
            name_lbl = QLabel(self.current_user_name())
            name_lbl.setObjectName("cashierName")
            role_lbl = QLabel("Cashier")
            role_lbl.setObjectName("cashierRole")
            details.addWidget(name_lbl)
            details.addWidget(role_lbl)

            top_row.addWidget(avatar)
            top_row.addLayout(details, 1)
            profile_layout.addLayout(top_row)

            status_lbl = QLabel("● Online")
            status_lbl.setObjectName("cashierStatus")
            profile_layout.addWidget(status_lbl, 0, Qt.AlignLeft)
            layout.addWidget(profile_card)
        else:
            decor = QLabel("o o o")
            decor.setObjectName("sidebarDecor")
            decor.setAlignment(Qt.AlignRight)
            layout.addWidget(decor)

            divider = QFrame()
            divider.setObjectName("sidebarDivider")
            layout.addWidget(divider)

        exit_btn = QPushButton("Logout" if self.is_cashier_role() else "Exit to Home")
        exit_btn.setObjectName("exitBtn")
        exit_btn.setIcon(self.nav_icon("back.svg"))
        exit_btn.setIconSize(QSize(18, 18))
        exit_btn.setCursor(Qt.PointingHandCursor)
        exit_btn.clicked.connect(self.exit_to_home)
        layout.addWidget(exit_btn)

        return sidebar

    def stack_placeholder_page(self, label_text):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch()
        label = QLabel(f"Loading {label_text}...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size:18px; font-weight:800; color:#8c796d; background:transparent;")
        layout.addWidget(label)
        layout.addStretch()
        return page

    def ensure_stack_page_loaded(self, index, force_rebuild=False):
        if not hasattr(self, "stack") or self.stack.count() <= index:
            return None
        if index < 0 or index >= len(self._stack_builder_names):
            return self.stack.widget(index)

        builder_name = self._stack_builder_names[index]
        if not builder_name:
            return self.stack.widget(index)

        if not force_rebuild and index in self._loaded_stack_pages:
            return self.stack.widget(index)

        old_page = self.stack.widget(index)
        old_vertical_value = None
        old_horizontal_value = None
        if isinstance(old_page, QScrollArea):
            old_vertical_value = old_page.verticalScrollBar().value()
            old_horizontal_value = old_page.horizontalScrollBar().value()

        new_page = getattr(self, builder_name)()
        self.stack.removeWidget(old_page)
        old_page.deleteLater()
        self.stack.insertWidget(index, new_page)
        self._loaded_stack_pages.add(index)
        self._dirty_page_builders.pop(index, None)

        if isinstance(new_page, QScrollArea) and old_vertical_value is not None:
            def restore_scroll_position():
                try:
                    new_page.verticalScrollBar().setValue(old_vertical_value)
                    if old_horizontal_value is not None:
                        new_page.horizontalScrollBar().setValue(old_horizontal_value)
                except RuntimeError:
                    pass

            QTimer.singleShot(0, restore_scroll_position)

        return new_page

    def build_main_stack(self):
        self.stack = QStackedWidget()
        self._stack_builder_names = []
        self._loaded_stack_pages = set()
        for index, (label, _, builder) in enumerate(self.navigation_pages()):
            builder_name = getattr(builder, "__name__", "")
            self._stack_builder_names.append(builder_name)
            if index == 0:
                self.stack.addWidget(builder())
                self._loaded_stack_pages.add(index)
            else:
                self.stack.addWidget(self.stack_placeholder_page(label))
        self.switch_page(0)
        return self.stack

    def switch_page(self, index):
        self.ensure_stack_page_loaded(index)
        self.stack.setCurrentIndex(index)
        self._apply_nav_button_state(index)
        current_page = self.stack.widget(index) if hasattr(self, "stack") and self.stack.count() > index else None
        if current_page is getattr(self, "products_page_scroll", None):
            self.schedule_refresh_products_ui(60)
        if index in self._dirty_page_builders:
            self._schedule_page_refresh(index, 0)

    def schedule_refresh_products_ui(self, delay_ms=120):
        if not hasattr(self, "_product_refresh_timer") or self._product_refresh_timer is None:
            self.refresh_products_ui()
            return
        self._product_refresh_timer.start(max(0, int(delay_ms)))

    def build_scroll_page(self, content_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content_widget)
        return scroll

    def page_header(self, title, subtitle, action_widget=None):
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        t = QLabel(title)
        t.setObjectName("pageTitle")
        s = QLabel(subtitle)
        s.setObjectName("pageSub")

        text_col.addWidget(t)
        text_col.addWidget(s)

        right_wrap = QWidget()
        right_wrap.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        right_col = QVBoxLayout(right_wrap)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(6)

        decor = QLabel("\u25CC\u25CC\u25CC")
        decor.setObjectName("sidebarDecor")
        decor.setAlignment(Qt.AlignRight)
        right_col.addWidget(decor, 0, Qt.AlignRight)

        datetime_wrap = QWidget()
        datetime_wrap.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        datetime_col = QVBoxLayout(datetime_wrap)
        datetime_col.setContentsMargins(0, 0, 0, 0)
        datetime_col.setSpacing(0)

        time_lbl = QLabel()
        time_lbl.setAlignment(Qt.AlignRight)
        time_lbl.setStyleSheet(
            "font-size:22px; font-weight:900; color:#7a6e66; background:transparent;"
        )

        date_lbl = QLabel()
        date_lbl.setAlignment(Qt.AlignRight)
        date_lbl.setStyleSheet(
            "font-size:13px; font-weight:700; color:#9a8f86; background:transparent;"
        )

        self.clock_labels.append(time_lbl)
        self.date_labels.append(date_lbl)

        datetime_col.addWidget(time_lbl)
        datetime_col.addWidget(date_lbl)
        time_notif_row = QHBoxLayout()
        time_notif_row.setContentsMargins(0, 0, 0, 0)
        time_notif_row.setSpacing(10)
        time_notif_row.addWidget(datetime_wrap, 0, Qt.AlignRight)
        time_notif_row.addWidget(self.notification_trigger_button(), 0, Qt.AlignRight | Qt.AlignVCenter)
        right_col.addLayout(time_notif_row)

        if action_widget is not None:
            right_col.addWidget(action_widget, 0, Qt.AlignRight)

        layout.addLayout(text_col, 1)
        layout.addStretch()
        layout.addWidget(right_wrap, 0, Qt.AlignTop | Qt.AlignRight)
        return wrap

    def start_datetime_updates(self):
        self.datetime_timer = QTimer(self)
        self.datetime_timer.timeout.connect(self.update_datetime_labels)
        self.update_datetime_labels()
        self.datetime_timer.start(1000)

    def start_live_monitoring(self):
        self.refresh_live_monitoring_data(show_toasts=False)
        self.live_monitor_timer = QTimer(self)
        self.live_monitor_timer.timeout.connect(self.refresh_live_monitoring_data)
        self.live_monitor_timer.start(30000)

    def notification_signature(self, notification):
        return (
            str(notification.get("kind", "")).strip(),
            str(notification.get("title", "")).strip(),
            str(notification.get("message", "")).strip(),
        )

    def refresh_notification_center_if_open(self):
        popup = self.notification_popup
        if popup is None:
            return
        try:
            if popup.isVisible():
                notifications = self.notification_items()
                popup.close()
                self.notification_popup = NotificationCenterPopup(self, notifications)
                self.notification_popup.adjustSize()
                x = self.x() + self.width() - self.notification_popup.width() - 34
                y = self.y() + 86
                self.notification_popup.move(max(10, x), max(10, y))
                self.notification_popup.show()
            else:
                self.notification_popup = None
        except RuntimeError:
            self.notification_popup = None

    def refresh_live_monitoring_data(self, show_toasts=True):
        if self._live_monitor_refresh_in_progress:
            return
        self._live_monitor_refresh_in_progress = True
        self._live_monitor_tick += 1
        try:
            try:
                database.sync_from_mysql_if_due(force=False, min_interval_seconds=20.0)
            except Exception:
                pass
            inventory_before = getattr(self, "inventory_items", [])
            products_before = getattr(self, "products", [])
            schedule_before = dict(getattr(self, "shop_schedule", {}) or {})

            self.shop_schedule = self.load_shop_schedule_from_database()
            self.inventory_items = self.load_inventory_from_database()
            if self._live_monitor_tick % 6 == 1:
                self.products = self.load_products_from_database()

            inventory_changed = self.inventory_items != inventory_before
            products_changed = self.products != products_before
            schedule_changed = dict(self.shop_schedule or {}) != schedule_before

            notifications = self.notification_items()
            signatures = {self.notification_signature(item) for item in notifications}

            if show_toasts:
                new_notifications = [
                    item for item in notifications
                    if self.notification_signature(item) not in self.notification_state_cache
                    and str(item.get("title", "")).strip().lower() != "system is normal"
                ]
                for item in new_notifications[:3]:
                    self.show_notification(
                        item.get("title", "Notification"),
                        item.get("message", ""),
                        item.get("kind", "info"),
                        3400,
                    )

            self.notification_state_cache = signatures
            self.update_notification_badges()
            self.refresh_notification_center_if_open()

            if inventory_changed or products_changed or schedule_changed:
                self.refresh_connected_views(include_products=products_changed)
                self.refresh_inventory_page_if_visible()
        finally:
            self._live_monitor_refresh_in_progress = False

    def update_datetime_labels(self):
        now = QDateTime.currentDateTime()
        current_time = now.toString("h:mm:ss AP")
        current_date = now.toString("dddd, MMMM d, yyyy")

        active_clock_labels = []
        for label in self.clock_labels:
            try:
                label.setText(current_time)
                active_clock_labels.append(label)
            except RuntimeError:
                continue
        self.clock_labels = active_clock_labels

        active_date_labels = []
        for label in self.date_labels:
            try:
                label.setText(current_date)
                active_date_labels.append(label)
            except RuntimeError:
                continue
        self.date_labels = active_date_labels
        self.update_notification_badges()

    def show_notification(self, title, text, kind="info", duration_ms=2600):
        toast = ToastNotification(self, title, text, kind=kind, duration_ms=duration_ms)
        self.active_notifications.append(toast)
        toast.show()
        toast.adjustSize()
        self.reposition_notifications()
        return toast

    def remove_notification(self, toast):
        self.active_notifications = [item for item in self.active_notifications if item is not toast]
        self.reposition_notifications()

    def reposition_notifications(self):
        right_margin = 24
        top_margin = 24
        gap = 12
        y = top_margin
        alive = []
        for toast in self.active_notifications:
            if toast and not toast.isHidden():
                toast.adjustSize()
                x = max(12, self.width() - toast.width() - right_margin)
                toast.move(x, y)
                y += toast.height() + gap
                alive.append(toast)
        self.active_notifications = alive

    def notification_trigger_button(self):
        wrap = QFrame()
        wrap.setStyleSheet("background:transparent; border:none;")
        wrap.setFixedSize(46, 46)

        button = QPushButton("🔔", wrap)
        button.setCursor(Qt.PointingHandCursor)
        button.setGeometry(0, 0, 46, 46)
        button.setStyleSheet("""
            QPushButton {
                background:#fff8f2;
                color:#9c6636;
                border:1px solid #ead8c8;
                border-radius:14px;
                font-size:18px;
                font-weight:900;
            }
            QPushButton:hover {
                background:#fdf1e6;
            }
        """)
        button.clicked.connect(self.open_notification_center)

        badge = QLabel("0", wrap)
        badge.setAlignment(Qt.AlignCenter)
        badge.setGeometry(30, -2, 18, 18)
        badge.setStyleSheet("""
            background:#b94b37;
            color:white;
            border:none;
            border-radius:9px;
            font-size:10px;
            font-weight:900;
        """)

        self.notification_buttons.append(button)
        self.notification_badges.append(badge)
        self.update_notification_badges()
        return wrap

    def notification_items(self):
        notifications = []
        low_stock_items = self.live_low_stock_items()
        out_items = [item for item in low_stock_items if str(item.get("status", "")).strip().lower() == "out"]
        low_items = [item for item in low_stock_items if str(item.get("status", "")).strip().lower() == "low"]
        unavailable_products = [product for product in getattr(self, "products", []) if not product.get("available", True)]

        if out_items:
            item_names = ", ".join(item.get("name", "Item") for item in out_items[:3])
            notifications.append({
                "kind": "error",
                "icon": "!",
                "title": "Out of stock items",
                "message": f"Restock now: {item_names}. Orders may be affected.",
                "action_label": "Open Inventory",
                "action": self.handle_quick_add_stock,
            })

        if low_items:
            item_names = ", ".join(item.get("name", "Item") for item in low_items[:3])
            notifications.append({
                "kind": "warning",
                "icon": "!",
                "title": "Low stock warning",
                "message": f"Monitor and restock soon: {item_names}.",
                "action_label": "Restock Items",
                "action": self.handle_quick_add_stock,
            })

        shop_status = str((self.shop_schedule or {}).get("shop_status", "CLOSED")).strip().upper()
        if shop_status == "OPEN":
            notifications.append({
                "kind": "success",
                "icon": "i",
                "title": "Shop is open",
                "message": f"The system is accepting orders until {self._schedule_time('closing_time', '23:00:00').toString('h:mm AP')}.",
                "action_label": "Open Orders",
                "action": self.handle_quick_new_order,
            })
        else:
            notifications.append({
                "kind": "info",
                "icon": "i",
                "title": "Shop is closed",
                "message": f"Orders will resume at {self._schedule_time('opening_time', '08:00:00').toString('h:mm AP')}.",
                "action_label": "View Reports",
                "action": self.handle_quick_view_reports,
            })

        if unavailable_products:
            product_names = ", ".join(product.get("name", "Product") for product in unavailable_products[:3])
            notifications.append({
                "kind": "warning",
                "icon": "!",
                "title": "Unavailable products found",
                "message": f"Check product availability: {product_names}.",
                "action_label": "Open Products",
                "action": lambda: self.switch_page(3),
            })

        if not notifications:
            notifications.append({
                "kind": "success",
                "icon": "i",
                "title": "System is normal",
                "message": "No urgent actions are needed right now.",
                "action_label": "Go to Dashboard",
                "action": lambda: self.switch_page(0),
            })

        return notifications

    def update_notification_badges(self):
        count = len(self.notification_items())
        active_badges = []
        for badge in self.notification_badges:
            try:
                badge.setText(str(count))
                badge.setVisible(count > 0)
                active_badges.append(badge)
            except RuntimeError:
                continue
        self.notification_badges = active_badges

        active_buttons = []
        for button in self.notification_buttons:
            try:
                button.setToolTip(f"{count} notification(s)")
                active_buttons.append(button)
            except RuntimeError:
                continue
        self.notification_buttons = active_buttons

    def open_notification_center(self):
        sender = self.sender()
        anchor_widget = sender if isinstance(sender, QWidget) else None
        notifications = self.notification_items()

        if self.notification_popup is not None:
            try:
                self.notification_popup.close()
            except RuntimeError:
                pass

        self.notification_popup = NotificationCenterPopup(self, notifications)
        self.notification_popup.adjustSize()

        if anchor_widget is not None:
            global_pos = anchor_widget.mapToGlobal(anchor_widget.rect().bottomRight())
            x = global_pos.x() - self.notification_popup.width() + anchor_widget.width()
            y = global_pos.y() + 8
        else:
            x = self.x() + self.width() - self.notification_popup.width() - 34
            y = self.y() + 86

        self.notification_popup.move(max(10, x), max(10, y))
        self.notification_popup.show()

    def metric_card(self, title, value, icon, icon_bg):
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("variant", "metricCard")
        card.setFixedHeight(104)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        palette = {
            "Total Products": ("#8b654a", "#6f4d37", "#fffdf8", "#f5e7db", "#6f4a34"),
            "Today's Orders": ("#aa7442", "#8b5a30", "#fffdf8", "#f8eadc", "#7d522d"),
            "Total Revenue": ("#ca7a42", "#b7642f", "#fffdf8", "#f8eadc", "#a95526"),
            "Low Stock Items": ("#a24e36", "#8c3f2b", "#fffdf8", "#f5ddd6", "#7e3324"),
            "Total Time Slots": ("#8b654a", "#6f4d37", "#fffdf8", "#f5e7db", "#6f4a34"),
            "Total Orders Logged": ("#aa7442", "#8b5a30", "#fffdf8", "#f8eadc", "#7d522d"),
            "Most Active Slot": ("#9a5c3f", "#7d452d", "#fffdf8", "#f5e7db", "#71412b"),
        }
        bg1, bg2, value_color, title_color, icon_box = palette.get(
            title,
            ("#9a6d4b", "#81563a", "#fffdf8", "#f5e7db", "#734933")
        )
        card.setStyleSheet(f"""
            QFrame[variant="metricCard"] {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg1},
                    stop:1 {bg2}
                );
                border: 1px solid rgba(255, 240, 228, 0.16);
                border-radius: 18px;
            }}
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(26, 14, 24, 14)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(1)

        v = QLabel(value)
        v.setObjectName("metricValue")
        v.setStyleSheet(f"""
            color:{value_color};
            background:transparent;
            border:none;
            padding:0;
            margin:0;
            font-size:31px;
            font-weight:900;
            line-height:1.05;
        """)
        v.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        t = QLabel(title)
        t.setObjectName("metricTitle")
        t.setStyleSheet(f"""
            color:{title_color};
            background:transparent;
            border:none;
            padding:0;
            margin:0;
            font-size:15px;
            font-weight:800;
        """)
        t.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        left.addWidget(v)
        left.addWidget(t)
        left.addStretch(1)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(56, 56)
        icon_lbl.setStyleSheet(f"""
            background: {icon_box};
            border-radius: 16px;
            font-size: 24px;
            color: #fffaf4;
            border: 1px solid rgba(255, 239, 227, 0.12);
        """)

        layout.addLayout(left, 1)
        layout.addStretch()
        layout.addWidget(icon_lbl, 0, Qt.AlignVCenter | Qt.AlignRight)

        return card

    def section_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        layout.addWidget(title_lbl)

        return card, layout

    def dashboard_panel_card(self):
        card = QFrame()
        card.setProperty("variant", "dashboardPanel")
        card.setStyleSheet("""
            QFrame[variant="dashboardPanel"] {
                background:#fffdfb;
                border:1px solid #efdece;
                border-radius:28px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(16)
        return card, layout

    def begin_busy_feedback(self, title, message, kind="info", duration_ms=1800):
        toast = self.show_notification(title, message, kind, duration_ms)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        return toast

    def end_busy_feedback(self):
        QApplication.processEvents()
        QApplication.restoreOverrideCursor()

    def dashboard_section_icon(self, text):
        icon_map = {
            "Top Products": "🥤",
            "Recent Activity": "🕘",
            "Low Stock Alerts": "⚠",
            "Inventory Status": "📦",
            "Sales Analytics": "📈",
            "Order Summary": "🧾",
        }
        icon = QLabel(icon_map.get(str(text).strip(), str(text).strip() or "•"))
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(46, 46)
        icon.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fffaf3, stop:1 #f7ead8);
            color:#ac6d31;
            border:1px solid #eddcca;
            border-radius:23px;
            font-size:22px;
            font-weight:900;
        """)
        return icon

    def dashboard_panel_header(self, icon_text, title, action_text=None):
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.dashboard_section_icon(title or icon_text))

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:27px; font-weight:900; color:#4a2a18;")
        layout.addWidget(title_lbl)
        layout.addStretch()

        if action_text:
            chip = QPushButton(action_text)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet("""
                QPushButton {
                    background:#fffaf5;
                    color:#9c6636;
                    border:1px solid #ebcfb6;
                    border-radius:14px;
                    padding:10px 18px;
                    font-size:13px;
                    font-weight:800;
                }
                QPushButton:hover { background:#fdf2e8; }
            """)
            layout.addWidget(chip, 0, Qt.AlignRight)
            return wrap, chip

        return wrap, None

    def dashboard_header(self):
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(4)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size:26px; font-weight:900; color:#20150f;")
        subtitle = QLabel(self.dashboard_welcome_subtitle())
        subtitle.setStyleSheet("font-size:14px; color:#8c796d;")
        left.addWidget(title)
        left.addWidget(subtitle)

        time_col = QVBoxLayout()
        time_col.setSpacing(0)
        time_lbl = QLabel()
        time_lbl.setAlignment(Qt.AlignRight)
        time_lbl.setStyleSheet("font-size:17px; font-weight:900; color:#5f5148;")
        date_lbl = QLabel()
        date_lbl.setAlignment(Qt.AlignRight)
        date_lbl.setStyleSheet("font-size:13px; font-weight:700; color:#8f7c6f;")
        self.clock_labels.append(time_lbl)
        self.date_labels.append(date_lbl)
        time_col.addWidget(time_lbl)
        time_col.addWidget(date_lbl)

        right = QHBoxLayout()
        right.setSpacing(10)
        right.addLayout(time_col)
        right.addWidget(self.notification_trigger_button(), 0, Qt.AlignVCenter)

        layout.addLayout(left, 1)
        layout.addLayout(right)
        return wrap

    def dashboard_filter_chip(self, text):
        chip = QPushButton(text)
        chip.setStyleSheet("""
            QPushButton {
                background:#fff8f2;
                color:#8d613f;
                border:1px solid #ead8c8;
                border-radius:12px;
                padding:8px 14px;
                font-size:12px;
                font-weight:800;
            }
        """)
        return chip

    def analytics_metric_card(self, title, value, subtitle, icon_text, start_color, end_color):
        icon_map = {
            "Total Products": "☕",
            "Today's Orders": "🧾",
            "Total Revenue": "₱",
            "Low Stock Items": "⚠",
        }
        card = QFrame()
        card.setProperty("variant", "analyticsMetricCard")
        card.setMinimumHeight(104)
        card.setMaximumHeight(104)
        card.setStyleSheet(f"""
            QFrame[variant="analyticsMetricCard"] {{
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {start_color}, stop:1 {end_color});
                border:none;
                border-radius:20px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 14, 18, 14)
        layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("font-size:24px; font-weight:900; color:white; border:none; background:transparent;")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:13px; font-weight:900; color:white; border:none; background:transparent;")
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setStyleSheet("font-size:11px; color:rgba(255, 247, 239, 0.84); border:none; background:transparent;")
        text_col.addWidget(value_lbl)
        text_col.addWidget(title_lbl)
        text_col.addWidget(subtitle_lbl)

        icon_chip = QLabel(icon_map.get(title, icon_text))
        icon_chip.setAlignment(Qt.AlignCenter)
        icon_chip.setFixedSize(54, 54)
        icon_chip.setStyleSheet("""
            background:rgba(92, 49, 27, 0.26);
            color:#fff8f1;
            border-radius:16px;
            border:1px solid rgba(255, 237, 221, 0.12);
            font-size:21px;
            font-weight:900;
        """)

        layout.addLayout(text_col, 1)
        layout.addWidget(icon_chip, 0, Qt.AlignVCenter | Qt.AlignRight)
        return card

    def analytics_header(self, action_widget=None):
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 8, 0, 0)
        top_row.setSpacing(12)

        title = QLabel("Sales Analytics")
        title.setObjectName("pageTitle")
        top_row.addWidget(title)
        top_row.addStretch()

        time_col = QVBoxLayout()
        time_col.setContentsMargins(0, 6, 0, 0)
        time_col.setSpacing(0)

        time_lbl = QLabel()
        time_lbl.setAlignment(Qt.AlignRight)
        time_lbl.setStyleSheet("font-size:22px; font-weight:900; color:#7a6e66; background:transparent;")
        date_lbl = QLabel()
        date_lbl.setAlignment(Qt.AlignRight)
        date_lbl.setStyleSheet("font-size:13px; font-weight:700; color:#9a8f86; background:transparent;")

        self.clock_labels.append(time_lbl)
        self.date_labels.append(date_lbl)

        time_col.addWidget(time_lbl, 0, Qt.AlignRight)
        time_col.addWidget(date_lbl, 0, Qt.AlignRight)
        top_row.addLayout(time_col)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(12)

        subtitle = QLabel("Track your business performance")
        subtitle.setObjectName("pageSub")
        bottom_row.addWidget(subtitle)
        bottom_row.addStretch()
        if action_widget is not None:
            bottom_row.addWidget(action_widget, 0, Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(top_row)
        layout.addLayout(bottom_row)
        return wrap

    def inventory_toolbar_chip(self, text, with_arrow=False, dark=False):
        btn = QPushButton(f"{text}  ▾" if with_arrow else text)
        if dark:
            btn.setStyleSheet("""
                QPushButton {
                    background:#9b5e34;
                    color:white;
                    border:none;
                    border-radius:12px;
                    padding:11px 18px;
                    font-size:13px;
                    font-weight:800;
                }
                QPushButton:hover { background:#824c28; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background:#fffaf5;
                    color:#735846;
                    border:1px solid #e8d8ca;
                    border-radius:12px;
                    padding:11px 18px;
                    font-size:13px;
                    font-weight:700;
                }
            """)
        return btn

    def inventory_item_icon(self, text, accent):
        icon = QLabel(text)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(52, 52)
        icon.setStyleSheet(f"""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e4d0bf, stop:0.55 #bf9b81, stop:1 #6b4a35);
            color:#fffdf9;
            border:1px solid #d8c0ac;
            border-radius:18px;
            font-size:17px;
            font-weight:900;
        """)
        return icon

    def inventory_info_chip(self, text, kind="neutral"):
        chip = QLabel(str(text))
        chip.setAlignment(Qt.AlignCenter)

        palette = {
            "neutral": ("#fbf5ee", "#f0e4d7", "#7a6352"),
            "stock": ("#f7efe7", "#efe1d1", "#34231a"),
            "reorder": ("#fbf4ec", "#f0e2d2", "#6a5445"),
            "category": ("#fcf7f1", "#f3e7db", "#856b58"),
        }
        bg, border, color = palette.get(kind, palette["neutral"])
        chip.setStyleSheet(f"""
            background:{bg};
            color:{color};
            border:1px solid {border};
            border-radius:17px;
            padding:8px 16px;
            font-size:13px;
            font-weight:700;
        """)
        return chip

    def inventory_status_badge(self, status):
        badge = QLabel(status)
        badge.setAlignment(Qt.AlignCenter)
        normalized = str(status).strip().lower()
        if normalized == "good":
            badge.setStyleSheet("""
                background:#eaf8e8;
                color:#5d9b58;
                border:1px solid #d4ebd1;
                border-radius:17px;
                padding:8px 16px;
                font-size:13px;
                font-weight:800;
            """)
        elif normalized == "low":
            badge.setStyleSheet("""
                background:#fdeceb;
                color:#bf4b3f;
                border:1px solid #f3c9c4;
                border-radius:17px;
                padding:8px 16px;
                font-size:13px;
                font-weight:900;
            """)
        else:
            badge.setStyleSheet("""
                background:#fff0ec;
                color:#c85a45;
                border:1px solid #f1d0c7;
                border-radius:17px;
                padding:8px 16px;
                font-size:13px;
                font-weight:800;
            """)
        return badge

    def make_dashboard_action_clickable(self, widget, handler):
        widget.setCursor(Qt.PointingHandCursor)
        widget.setStyleSheet((widget.styleSheet() or "") + "\nQWidget { }")

        def on_click(event):
            if event.button() == Qt.LeftButton:
                handler()

        widget.mousePressEvent = on_click

    def handle_quick_add_product(self):
        if self.is_cashier_role():
            self.switch_to_builder("page_cashier_products")
            self.show_notification("Access Denied", "Only admins can add products.", "warning", 2400)
            return
        self.switch_to_builder("page_products")
        self.open_add_product()

    def handle_quick_new_order(self):
        self.switch_to_builder("page_cashier_products" if self.is_cashier_role() else "page_orders")

    def handle_quick_add_stock(self):
        if self.is_cashier_role():
            self.switch_to_builder("page_cashier_orders")
            self.show_notification("Access Denied", "Only admins can restock inventory.", "warning", 2400)
            return
        self.switch_to_builder("page_inventory")

    def handle_quick_view_reports(self):
        self.switch_to_builder("page_cashier_receipts" if self.is_cashier_role() else "page_analytics")

    def handle_add_inventory_item(self):
        dlg = AddInventoryItemDialog(self)
        if dlg.exec_():
            try:
                self.begin_busy_feedback("Saving Inventory", "Adding the new inventory item...")
                self.controller.create_inventory_item({
                    "name": dlg.name_input.text().strip() or "New Inventory Item",
                    "category": dlg.category_input.text().strip() or "General",
                    "unit": dlg.unit_combo.currentText().strip() or "pieces",
                    "quantity_on_hand": dlg.quantity_input.value(),
                    "reorder_level": dlg.reorder_input.value(),
                })
                self.inventory_items = self.load_inventory_from_database()
                self.refresh_inventory_page_if_visible()
                self.show_notification("Inventory Saved", "New inventory item added successfully.", "success")
            except Exception as e:
                self.show_notification("Save Error", f"Cannot save inventory item:\n{e}", "error", 3400)
            finally:
                self.end_busy_feedback()

    def update_inventory_filter_button(self, button, value, default_label):
        display_value = value if value != default_label else default_label
        if len(display_value) > 16:
            display_value = f"{display_value[:13]}..."
        button.setText(display_value)
        button.setToolTip(value)

    def set_inventory_category_filter(self, value):
        self.inventory_category_filter_value = value
        if hasattr(self, "inventory_category_btn"):
            self.update_inventory_filter_button(self.inventory_category_btn, value, "All Categories")
        self.filter_inventory_rows()

    def set_inventory_status_filter(self, value):
        self.inventory_status_filter_value = value
        if hasattr(self, "inventory_status_btn"):
            self.update_inventory_filter_button(self.inventory_status_btn, value, "All Status")
        self.filter_inventory_rows()

    def filter_inventory_rows(self):
        if not hasattr(self, "inventory_row_widgets"):
            return

        search_text = self.inventory_search_input.text().strip().lower() if hasattr(self, "inventory_search_input") else ""
        selected_category = getattr(self, "inventory_category_filter_value", "All Categories")
        selected_status = getattr(self, "inventory_status_filter_value", "All Status")

        for row_widget, item in self.inventory_row_widgets:
            name = str(item.get("name", "")).lower()
            category = str(item.get("category", ""))
            status = str(item.get("status", ""))
            stock = str(item.get("stock", "")).lower()

            matches_search = (
                not search_text or
                search_text in name or
                search_text in category.lower() or
                search_text in stock
            )
            matches_category = selected_category == "All Categories" or category == selected_category
            matches_status = selected_status == "All Status" or status == selected_status
            row_widget.setVisible(matches_search and matches_category and matches_status)

    def normalize_inventory_name(self, name):
        return self.controller.normalize_inventory_name(name)

    def inventory_consumption_plan(self, product, order_config):
        return self.controller.inventory_consumption_plan(product, order_config, getattr(self, "inventory_items", []))

    def apply_inventory_deduction_for_order(self, product, order_config):
        plan = self.inventory_consumption_plan(product, order_config)
        if not plan:
            return

        try:
            for inventory_id, amount in plan.items():
                self.controller.consume_inventory_item(inventory_id, amount)

            self.inventory_items = self.load_inventory_from_database()
            self.refresh_inventory_page_if_visible()
            self.refresh_connected_views()
        except Exception as e:
            self.show_notification("Inventory Warning", f"Order was added, but inventory could not be updated:\n{e}", "warning", 3600)

    def analytics_status_row(self, color, label, count, percent):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        row.setStyleSheet("""
            QWidget {
                background:rgba(255, 252, 248, 0.92);
                border:1px solid #efe0d2;
                border-radius:14px;
            }
        """)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{color}; border-radius:5px;")
        text = QLabel(label)
        text.setStyleSheet("font-size:13px; color:#5e4a3d; border:none;")
        count_lbl = QLabel(str(count))
        count_lbl.setStyleSheet("font-size:13px; font-weight:800; color:#241913; border:none;")
        pct_lbl = QLabel(percent)
        pct_lbl.setStyleSheet("font-size:13px; color:#8f7f74; border:none;")
        layout.addWidget(dot)
        layout.addWidget(text, 1)
        layout.addWidget(count_lbl)
        layout.addSpacing(16)
        layout.addWidget(pct_lbl)
        return row

    def order_summary_item(self, icon_text, label_text, value_text):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background:rgba(255, 252, 248, 0.96);
                border:1px solid #ecdccd;
                border-radius:16px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(34, 34)
        icon.setStyleSheet("""
            background:#fbf1e7;
            color:#8b5638;
            border:1px solid #efdfd2;
            border-radius:11px;
            font-size:16px;
            font-weight:900;
        """)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        label = QLabel(label_text)
        label.setStyleSheet("font-size:12px; color:#7b6e66;")
        value = QLabel(value_text)
        value.setStyleSheet("font-size:20px; font-weight:900; color:#241610;")
        text_col.addWidget(label)
        text_col.addWidget(value)

        layout.addWidget(icon)
        layout.addLayout(text_col, 1)
        return card, value

    def analytics_performance_row(self, product, max_units):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        name = QLabel(product["name"])
        name.setStyleSheet("font-size:13px; color:#34231a;")
        name.setMinimumWidth(170)

        bar_wrap = QFrame()
        bar_wrap.setFixedHeight(10)
        bar_wrap.setStyleSheet("""
            background:#f2e6db;
            border:1px solid #eadacd;
            border-radius:5px;
        """)
        inner = QFrame(bar_wrap)
        width = 0 if max_units <= 0 else max(10 if product["units"] > 0 else 0, int((product["units"] / max_units) * 280))
        inner.setGeometry(0, 0, width, 10)
        inner.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8d5d34, stop:1 #b47a41);
            border-radius:5px;
        """)
        bar_wrap.setMinimumWidth(300)

        units = QLabel(str(product["units"]))
        units.setAlignment(Qt.AlignCenter)
        units.setStyleSheet("font-size:13px; color:#34231a;")
        units.setFixedWidth(70)

        revenue = QLabel(f"\u20b1{product['revenue']}")
        revenue.setAlignment(Qt.AlignCenter)
        revenue.setStyleSheet("font-size:13px; color:#34231a;")
        revenue.setFixedWidth(90)

        status = QLabel(product["status"])
        status.setAlignment(Qt.AlignCenter)
        status_color = "#f5cd67" if product["status"] == "Medium" else "#f3b1a6"
        text_color = "#6b5518" if product["status"] == "Medium" else "#9b4a3a"
        status.setStyleSheet(f"""
            background:{status_color};
            color:{text_color};
            border-radius:10px;
            padding:4px 10px;
            font-size:12px;
            font-weight:800;
        """)
        status.setFixedWidth(76)

        layout.addWidget(name)
        layout.addWidget(bar_wrap, 1)
        layout.addWidget(units)
        layout.addWidget(revenue)
        layout.addWidget(status)
        return row

    def product_thumb(self, accent, emoji, size=42, radius=12, font_size=17):
        thumb = QLabel(emoji)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(size, size)
        thumb.setStyleSheet(f"""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff7f0, stop:1 {accent});
            border:1px solid #ead8c8;
            border-radius:{radius}px;
            color:#ffffff;
            font-size:{font_size}px;
            font-weight:900;
        """)
        return thumb

    def dashboard_status_box(self, value, label, bg_color, value_color):
        box = QFrame()
        box.setFixedHeight(62)
        box.setStyleSheet(f"""
            QFrame {{
                background:{bg_color};
                border:none;
                border-radius:14px;
            }}
        """)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(1)
        number = QLabel(str(value))
        number.setAlignment(Qt.AlignCenter)
        number.setStyleSheet(f"font-size:17px; font-weight:900; color:{value_color}; background:transparent; border:none;")
        text = QLabel(label)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(f"font-size:12px; font-weight:700; color:{value_color}; background:transparent; border:none;")
        layout.addStretch()
        layout.addWidget(number)
        layout.addWidget(text)
        layout.addStretch()
        return box

    def dashboard_product_row(self, product):
        row = QFrame()
        row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        row.setStyleSheet("""
            QFrame {
                background:transparent;
                border:none;
                border-bottom:1px solid #efe2d5;
            }
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        thumb = QLabel()
        thumb.setFixedSize(64, 64)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            background:#f4e5d7;
            border:1px solid #ead5c3;
            border-radius:14px;
            color:#7f5a43;
            font-size:13px;
            font-weight:800;
        """)
        rendered = self.render_product_image(
            product.get("image", ""),
            QSize(64, 64),
            self.product_image_background(product.get("subtitle", ""))
        )
        if rendered:
            thumb.setPixmap(rendered)
        else:
            fallback_name = str(product.get("name", "P")).strip()
            thumb.setText("".join(word[0] for word in fallback_name.split()[:2]).upper() or "PR")
        layout.addWidget(thumb, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name = QLabel(product["name"])
        name.setStyleSheet("font-size:17px; font-weight:900; color:#2b1b14;")
        subtitle = QLabel(product["subtitle"])
        subtitle.setStyleSheet("font-size:12px; color:#8c796d;")
        text_col.addWidget(name)
        text_col.addWidget(subtitle)
        text_col.setAlignment(Qt.AlignTop)

        price_col = QVBoxLayout()
        price_col.setSpacing(2)
        price = QLabel(product["price"])
        price.setAlignment(Qt.AlignRight)
        price.setStyleSheet("font-size:17px; font-weight:900; color:#2e1d14;")
        sold = QLabel(product["sold"])
        sold.setAlignment(Qt.AlignRight)
        sold.setStyleSheet("font-size:12px; color:#8c796d;")
        price_col.addWidget(price)
        price_col.addWidget(sold)
        price_col.setAlignment(Qt.AlignTop)

        layout.addLayout(text_col, 1)
        layout.addLayout(price_col, 0)
        return row

    def dashboard_fallback_top_products(self, limit=5):
        fallback = []
        for product in getattr(self, "products", [])[:limit]:
            name = str(product.get("name", "")).strip() or "Product"
            category = str(product.get("category", "Product")).strip() or "Product"
            price_text = str(product.get("price_text", "")).strip() or "\u20b10"
            fallback.append({
                "name": name,
                "subtitle": category,
                "price": price_text,
                "sold": "0 sold",
                "image": product.get("image", ""),
            })

        if fallback:
            return fallback

        return [{
            "name": "Classic Milk Tea",
            "subtitle": "Milk Tea",
            "price": "\u20b10",
            "sold": "0 sold",
            "image": "",
        }]

    def dashboard_low_stock_row(self, product):
        row = QFrame()
        row.setProperty("variant", "dashboardLowStockRow")
        row.setStyleSheet("""
            QFrame[variant="dashboardLowStockRow"] {
                background:#fffdfa;
                border:1px solid #f0e1d3;
                border-radius:18px;
            }
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)
        thumb_color = product.get("accent", "#b77746")
        thumb_text = product.get("emoji") or product.get("icon") or "IT"
        layout.addWidget(self.product_thumb(thumb_color, thumb_text, size=56, radius=14, font_size=19))

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        name = QLabel(product.get("name", "Inventory Item"))
        name.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        detail = QLabel(f"Current: {product.get('stock', '-')}  •  Reorder Level: {product.get('reorder', '-')}")
        detail.setStyleSheet("font-size:12px; color:#8c796d;")
        text_col.addWidget(name)
        text_col.addWidget(detail)

        badge = QLabel(str(product.get("stock", "-")))
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff3ef, stop:1 #ffe6de);
            color:#c54f3a;
            border:1px solid #f6d4ca;
            border-radius:12px;
            padding:10px 16px;
            font-size:14px;
            font-weight:900;
        """)
        badge.setMinimumWidth(72)

        action = QPushButton("Restock Now")
        action.setCursor(Qt.PointingHandCursor)
        action.setStyleSheet("""
            QPushButton {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d95b40, stop:1 #be4029);
                color:white;
                border:none;
                border-radius:12px;
                padding:12px 18px;
                font-size:13px;
                font-weight:900;
            }
            QPushButton:hover { background:#b9422c; }
        """)
        if product.get("id") is not None:
            action.clicked.connect(
                lambda checked=False, item_data=product: self.open_restock_dialog(
                    item_data.get("name", "Inventory Item"),
                    item_data.get("stock", "-"),
                    item_data.get("id")
                )
            )

        layout.addLayout(text_col, 1)
        layout.addWidget(badge)
        layout.addWidget(action)
        return row

    def dashboard_activity_row(self, color, icon_text, title, timestamp, activity_type="generic", product_name="", image_path=""):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        timeline = QWidget()
        timeline.setFixedWidth(54)
        timeline_layout = QVBoxLayout(timeline)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)
        line_top = QFrame()
        line_top.setFixedWidth(2)
        line_top.setMinimumHeight(10)
        line_top.setStyleSheet("background:#ead9c8; border:none;")
        line_bottom = QFrame()
        line_bottom.setFixedWidth(2)
        line_bottom.setMinimumHeight(42)
        line_bottom.setStyleSheet("background:#ead9c8; border:none;")

        icon = QLabel(icon_text)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(42, 42)
        icon.setStyleSheet(f"""
            background:{color};
            color:#fffaf5;
            border:4px solid #fff8f1;
            border-radius:21px;
            font-size:16px;
            font-weight:900;
        """)
        timeline_layout.addWidget(line_top, 0, Qt.AlignHCenter)
        timeline_layout.addWidget(icon, 0, Qt.AlignHCenter)
        timeline_layout.addWidget(line_bottom, 1, Qt.AlignHCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 10, 0, 12)
        text_col.setSpacing(6)
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet("font-size:12px; color:#8c796d;")
        text_col.addWidget(title_lbl)
        if activity_type.startswith("order") and product_name:
            product_lbl = QLabel(product_name)
            product_lbl.setStyleSheet("font-size:13px; font-weight:700; color:#8d6545;")
            text_col.addWidget(product_lbl)
        text_col.addWidget(time_lbl)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#f0e1d4; border:none; margin-top:10px;")
        text_col.addWidget(divider)

        layout.addWidget(timeline, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        if activity_type.startswith("order") and image_path:
            thumb = QLabel()
            thumb.setFixedSize(58, 58)
            thumb.setAlignment(Qt.AlignCenter)
            thumb.setStyleSheet("background:#f6ede4; border:1px solid #ead7c5; border-radius:14px;")
            rendered = self.render_product_image(image_path, QSize(58, 58), accent="#f6ede4")
            if rendered is not None and not rendered.isNull():
                thumb.setPixmap(rendered)
            else:
                thumb.setText("IMG")
                thumb.setStyleSheet("background:#f6ede4; border:1px solid #ead7c5; border-radius:14px; color:#9b7f6b; font-size:11px; font-weight:800;")
            layout.addWidget(thumb, 0, Qt.AlignTop)
        return row

    def product_image_label(self, image_path):
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedHeight(182)
        lbl.setStyleSheet("""
            background:transparent;
            border:none;
            border-radius:18px;
            color:#9b7f6b;
            font-size:16px;
            font-weight:700;
        """)

        if image_path:
            pix = self.prepare_product_pixmap(image_path)
            if pix and not pix.isNull():
                lbl.setPixmap(pix.scaled(240, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return lbl

        lbl.setText("Product Image")
        return lbl

    def render_product_image(self, image_path, canvas_size, accent="#efe1d3"):
        cache_key = (str(image_path or ""), int(canvas_size.width()), int(canvas_size.height()), str(accent))
        cached = self._rendered_product_image_cache.get(cache_key)
        if cached is not None:
            return cached

        pix = self.prepare_product_pixmap(image_path)
        if pix is None or pix.isNull():
            return None

        canvas = QPixmap(canvas_size)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        bg_rect = QRectF(0, 0, canvas_size.width(), canvas_size.height())
        painter.setPen(QPen(QColor("#e7d5c2"), 1))
        painter.setBrush(QColor(accent))
        painter.drawRoundedRect(bg_rect.adjusted(1, 1, -1, -1), 20, 20)

        inner_rect = bg_rect.adjusted(10, 10, -10, -10)
        scaled = pix.scaled(
            int(inner_rect.width()),
            int(inner_rect.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        x = int(inner_rect.x() + (inner_rect.width() - scaled.width()) / 2)
        y = int(inner_rect.y() + (inner_rect.height() - scaled.height()) / 2)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        self._rendered_product_image_cache[cache_key] = canvas
        return canvas

    def prepare_product_pixmap(self, image_path):
        cache_key = str(image_path or "")
        if cache_key in self._prepared_pixmap_cache:
            return self._prepared_pixmap_cache[cache_key]

        source = QPixmap(resolve_product_image_path(image_path))
        if source.isNull():
            self._prepared_pixmap_cache[cache_key] = None
            return None

        max_dimension = 720
        if source.width() > max_dimension or source.height() > max_dimension:
            source = source.scaled(max_dimension, max_dimension, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        image = source.toImage().convertToFormat(source.toImage().Format_ARGB32)
        width = image.width()
        height = image.height()

        for y in range(height):
            for x in range(width):
                color = QColor(image.pixel(x, y))
                if color.red() <= 45 and color.green() <= 45 and color.blue() <= 45:
                    color.setAlpha(0)
                    image.setPixelColor(x, y, color)

        prepared = QPixmap.fromImage(image)
        self._prepared_pixmap_cache[cache_key] = prepared
        return prepared

    def clear_product_image_caches(self):
        self._prepared_pixmap_cache.clear()
        self._rendered_product_image_cache.clear()

    def product_category_color(self, category):
        category_key = str(category or "").strip().lower()
        palette = {
            "classic": ("#b96f3b", "#fff5eb"),
            "signature": ("#dd8d2f", "#fff6e8"),
            "fruit tea": ("#8ebf50", "#f4ffe9"),
            "milk tea": ("#9b7ac8", "#f6efff"),
            "latte": ("#7aa54f", "#eff9e8"),
            "specialty": ("#a36d40", "#fdf1e7"),
        }
        return palette.get(category_key, ("#a36d40", "#fff5eb"))

    def product_image_background(self, category):
        category_key = str(category or "").strip().lower()
        palette = {
            "classic": "#f6e7d8",
            "signature": "#f4e1c6",
            "fruit tea": "#e4f0d8",
            "milk tea": "#ece4f6",
            "latte": "#e6efdc",
            "specialty": "#f2e2d6",
            "coffee": "#eadccf",
        }
        return palette.get(category_key, "#efe1d3")

    def product_status_badge(self, available):
        badge = QLabel("Available" if available else "Unavailable")
        badge.setAlignment(Qt.AlignCenter)
        bg = "#72c27f" if available else "#cf8a7f"
        badge.setStyleSheet(f"""
            background:{bg};
            color:white;
            border:none;
            border-radius:10px;
            padding:4px 10px;
            font-size:11px;
            font-weight:800;
        """)
        return badge

    def product_category_badge(self, category):
        text = category or "Category"
        bg, fg = self.product_category_color(text)
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background:{bg};
            color:{fg};
            border:none;
            border-radius:10px;
            padding:4px 10px;
            font-size:11px;
            font-weight:800;
        """)
        return badge

    def product_action_button(self, text, primary=False):
        label = text
        if "Edit" in text:
            label = "Edit"
        elif "Delete" in text:
            label = "Delete"

        btn = QPushButton(label)
        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background:#a9663b;
                    color:white;
                    border:none;
                    border-radius:10px;
                    padding:8px 14px;
                    font-size:12px;
                    font-weight:800;
                }
                QPushButton:hover { background:#8d5631; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background:#fff7ef;
                    color:#b36c3a;
                    border:1px solid #ecd8c5;
                    border-radius:10px;
                    padding:8px 14px;
                    font-size:12px;
                    font-weight:800;
                }
                QPushButton:hover { background:#f8ede1; }
            """)
        return btn

    def filtered_products(self):
        search_text = self.product_search_input.text().strip().lower() if hasattr(self, "product_search_input") else ""
        selected_category = self.product_category_filter.currentText() if hasattr(self, "product_category_filter") else "All Categories"

        filtered = []
        for product in self.products:
            name = str(product.get("name", "")).lower()
            desc = str(product.get("desc", "")).lower()
            category = str(product.get("category", ""))

            matches_search = not search_text or search_text in name or search_text in desc or search_text in category.lower()
            matches_category = selected_category == "All Categories" or category == selected_category

            if matches_search and matches_category:
                filtered.append(product)

        return filtered

    def refresh_product_filter_options(self):
        if not hasattr(self, "product_category_filter"):
            return

        current_value = self.product_category_filter.currentText()
        categories = sorted({product.get("category", "Classic") for product in self.products if product.get("category")})

        self.product_category_filter.blockSignals(True)
        self.product_category_filter.clear()
        self.product_category_filter.addItem("All Categories")
        self.product_category_filter.addItems(categories)

        index = self.product_category_filter.findText(current_value)
        self.product_category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.product_category_filter.blockSignals(False)

    def safe_int(self, value):
        try:
            raw = str(value).replace("\u20b1", "").replace(",", "").strip()
            if not raw:
                return 0
            filtered = "".join(ch for ch in raw if ch.isdigit() or ch == "-")
            return int(filtered or 0)
        except Exception:
            return 0

    def format_order_slot_label(self, start_hour):
        start = QTime(start_hour, 0).toString("h:mm AP")
        end = QTime((start_hour + 1) % 24, 0).toString("h:mm AP")
        return f"{start} - {end}"

    def build_default_order_rows(self):
        rows = []
        for hour in range(self.store_open_hour(), self.store_close_hour()):
            rows.append([self.format_order_slot_label(hour), "0", "0", "0", "0", "0", "0", "0"])
        return rows

    def can_accept_orders_now(self):
        current_time = QDateTime.currentDateTime().time()
        opening_time = self._schedule_time("opening_time", "08:00:00")
        closing_time = self._schedule_time("closing_time", "23:00:00")
        return opening_time <= current_time < closing_time

    def create_order_table_item(self, value="", editable=True, bold=False):
        item = QTableWidgetItem(str(value))
        item.setTextAlignment(Qt.AlignCenter)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        return item

    def order_data_row_count(self):
        if not hasattr(self, "orders_table"):
            return len(self.order_rows)
        return max(0, self.orders_table.rowCount() - 1)

    def initialize_orders_footer_row(self):
        footer_row = self.orders_table.rowCount() - 1

        for col in range(self.orders_table.columnCount()):
            self.orders_table.setItem(footer_row, col, self.create_order_table_item("", editable=False, bold=True))

        label_item = self.orders_table.item(footer_row, 0)
        label_item.setText("TOTAL FOR THE DAY")

        for col in range(self.orders_table.columnCount()):
            item = self.orders_table.item(footer_row, col)
            item.setBackground(QColor("#f4e8db"))
            item.setForeground(QColor("#6f4d37"))

    def update_orders_footer_row(self, milk_total, fruit_total, iced_coffee_total, milkshake_total, cream_base_total, total_orders, total_revenue):
        footer_row = self.orders_table.rowCount() - 1
        footer_values = {
            1: str(milk_total),
            2: str(fruit_total),
            3: str(iced_coffee_total),
            4: str(milkshake_total),
            5: str(cream_base_total),
            6: str(total_orders),
            7: f"\u20b1{total_revenue:,}",
        }
        for col, value in footer_values.items():
            item = self.orders_table.item(footer_row, col)
            if item is None:
                item = self.create_order_table_item("", editable=False, bold=True)
                self.orders_table.setItem(footer_row, col, item)
            item.setText(value)

    def sync_orders_table_from_order_rows(self):
        if not hasattr(self, "orders_table"):
            return

        self.orders_table.blockSignals(True)
        for row_idx, row_data in enumerate(self.order_rows):
            for col_idx, value in enumerate(row_data[:8]):
                item = self.orders_table.item(row_idx, col_idx)
                if item is None:
                    item = self.create_order_table_item(value, editable=(col_idx not in [0, 6]))
                    self.orders_table.setItem(row_idx, col_idx, item)
                else:
                    item.setText(str(value))
        self.orders_table.blockSignals(False)

    def build_summary_receipt(self):
        card = QFrame()
        card.setObjectName("summaryReceiptCard")
        card.setStyleSheet("""
            QFrame#summaryReceiptCard {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fffaf7, stop:1 #fff5ef);
                border:1px solid #ecdccf;
                border-radius:24px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(20)

        top = QHBoxLayout()
        top.setSpacing(12)

        title_wrap = QHBoxLayout()
        title_wrap.setSpacing(14)

        icon = QLabel("🗓")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(44, 44)
        icon.setStyleSheet("""
            background:rgba(181, 109, 53, 0.12);
            color:#9a5e34;
            border:1px solid #edd8c7;
            border-radius:14px;
            font-size:18px;
            font-weight:900;
        """)

        title = QLabel("Whole Day Summary")
        title.setStyleSheet("font-size:27px; font-weight:900; color:#5b3525; background:transparent;")

        self.summary_date_label = QLabel(self.active_summary_date_label())
        self.summary_date_label.setStyleSheet("font-size:16px; font-weight:700; color:#8a6b58; background:transparent;")

        title_wrap.addWidget(icon)
        title_wrap.addWidget(title)
        title_wrap.addStretch()

        top.addLayout(title_wrap, 1)
        top.addWidget(self.summary_date_label, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.summary_receipt_rows = {}
        rows = [
            ("total_orders", "🧾", "Total Orders", "-"),
            ("total_revenue", "₱", "Total Revenue", "-"),
            ("solo_cups", "🥤", "Solo Cups Used", "-"),
            ("large_cups", "🥤", "Large Cups Used", "-"),
            ("top_products", "★", "Top Products", "-"),
            ("low_stock", "⚠", "Low Stock Items", "-"),
        ]
        for key, icon_text, label_text, default_value in rows:
            row = QFrame()
            row.setObjectName("summaryReceiptRow")
            row.setStyleSheet("""
                QFrame#summaryReceiptRow {
                    background:transparent;
                    border:none;
                    border-radius:0;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 10, 8, 10)
            row_layout.setSpacing(18)

            row_icon = QLabel(icon_text)
            row_icon.setAlignment(Qt.AlignCenter)
            row_icon.setFixedSize(40, 40)
            row_icon.setStyleSheet("""
                background:transparent;
                color:#a05f36;
                border:none;
                font-size:18px;
                font-weight:900;
            """)

            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            label = QLabel(label_text)
            label.setStyleSheet("font-size:14px; color:#7a685d; background:transparent;")
            value = QLabel(default_value)
            value.setStyleSheet("font-size:20px; font-weight:900; color:#2a1a12; background:transparent;")
            value.setWordWrap(True)
            text_col.addWidget(label)
            text_col.addWidget(value)

            row_layout.addWidget(row_icon)
            row_layout.addLayout(text_col, 1)
            layout.addWidget(row)
            self.summary_receipt_rows[key] = value

        receipt_btn = QPushButton("View Full Report")
        receipt_btn.setStyleSheet("""
            QPushButton {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9a5e34, stop:1 #7f4b29);
                color:white;
                border:none;
                border-radius:16px;
                padding:16px 18px;
                font-size:15px;
                font-weight:900;
            }
            QPushButton:hover { background:#8a512d; }
        """)
        receipt_btn.clicked.connect(self.handle_quick_view_reports)
        layout.addWidget(receipt_btn)
        return card

    def update_summary_receipt_row(self, key, value):
        label = getattr(self, "summary_receipt_rows", {}).get(key)
        if label:
            label.setText(value)

    def summary_icon_pixmap(self, kind, icon_size=28, color="#a05f36"):
        canvas = QPixmap(icon_size, icon_size)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidth(max(2, icon_size // 12))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        def line(x1, y1, x2, y2):
            painter.drawLine(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))

        def point(x, y):
            painter.drawPoint(int(round(x)), int(round(y)))

        if kind == "calendar":
            body = QRectF(4, 6, icon_size - 8, icon_size - 10)
            painter.drawRoundedRect(body, 5, 5)
            line(body.left(), body.top() + 6, body.right(), body.top() + 6)
            line(body.left() + 6, 3, body.left() + 6, 9)
            line(body.right() - 6, 3, body.right() - 6, 9)
            for x in (body.left() + 7, body.center().x(), body.right() - 7):
                for y in (body.top() + 12, body.top() + 18):
                    point(x, y)
        elif kind == "receipt":
            body = QRectF(6, 3, icon_size - 12, icon_size - 6)
            painter.drawRoundedRect(body, 4, 4)
            line(body.left() + 4, body.top() + 7, body.right() - 4, body.top() + 7)
            line(body.left() + 5, body.top() + 13, body.right() - 5, body.top() + 13)
            line(body.left() + 5, body.top() + 18, body.right() - 9, body.top() + 18)
            line(body.left() + 5, body.top() + 23, body.right() - 12, body.top() + 23)
        elif kind == "coins":
            for offset in (8, 14, 20):
                painter.drawEllipse(QRectF(6, offset - 4, icon_size - 12, 7))
                if offset < 20:
                    line(6, offset, 6, offset + 6)
                    line(icon_size - 6, offset, icon_size - 6, offset + 6)
        elif kind == "solo_cup":
            cup = QPolygonF([
                QPointF(9, 10), QPointF(icon_size - 9, 10),
                QPointF(icon_size - 12, icon_size - 4), QPointF(12, icon_size - 4)
            ])
            painter.drawPolygon(cup)
            line(icon_size / 2, 4, icon_size / 2 + 4, 10)
            line(12, 15, icon_size - 12, 15)
        elif kind == "large_cup":
            cup = QPolygonF([
                QPointF(8, 8), QPointF(icon_size - 8, 8),
                QPointF(icon_size - 11, icon_size - 3), QPointF(11, icon_size - 3)
            ])
            painter.drawPolygon(cup)
            line(icon_size / 2 - 2, 3, icon_size / 2 + 3, 8)
            line(11, 14, icon_size - 11, 14)
        elif kind == "star":
            cx = icon_size / 2
            cy = icon_size / 2
            outer = icon_size / 2 - 4
            inner = outer * 0.45
            points = []
            for i in range(10):
                angle = -90 + i * 36
                radius = outer if i % 2 == 0 else inner
                x = cx + radius * math.cos(angle * 3.1415926535 / 180)
                y = cy + radius * math.sin(angle * 3.1415926535 / 180)
                points.append(QPointF(x, y))
            painter.drawPolygon(QPolygonF(points))
        elif kind == "warning":
            triangle = QPolygonF([
                QPointF(icon_size / 2, 4),
                QPointF(icon_size - 5, icon_size - 5),
                QPointF(5, icon_size - 5),
            ])
            painter.drawPolygon(triangle)
            line(icon_size / 2, 11, icon_size / 2, icon_size - 11)
            point(icon_size / 2, icon_size - 8)
        painter.end()
        return canvas

    def summary_icon_badge(self, kind, badge_size=56, icon_size=28):
        badge = QLabel()
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(badge_size, badge_size)
        badge.setPixmap(self.summary_icon_pixmap(kind, icon_size))
        badge.setStyleSheet("""
            background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff8f0, stop:1 #fceddf);
            border:1px solid #f1dfd0;
            border-radius:16px;
        """)
        return badge

    def build_summary_receipt_v2(self):
        card = QFrame()
        card.setObjectName("summaryReceiptCardV2")
        card.setStyleSheet("""
            QFrame#summaryReceiptCardV2 {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fffdfb, stop:0.58 #fff8f1, stop:1 #fff4ea);
                border:1px solid #ebdac9;
                border-radius:28px;
            }
            QFrame[summaryStat="true"] {
                background:rgba(255, 253, 250, 0.98);
                border:1px solid #eedfd2;
                border-radius:18px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(22)

        top = QHBoxLayout()
        top.setSpacing(16)

        title_wrap = QHBoxLayout()
        title_wrap.setSpacing(14)

        icon = self.summary_icon_badge("calendar", 50, 24)

        title = QLabel("Whole Day Summary")
        title.setStyleSheet("font-size:28px; font-weight:900; color:#5a3523; background:transparent;")

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title_col.addWidget(title)

        accent_line = QLabel("────  ●  ────")
        accent_line.setStyleSheet("font-size:12px; color:#c8a285; background:transparent;")
        title_col.addWidget(accent_line, 0, Qt.AlignLeft)

        self.summary_date_label = QLabel(self.active_summary_date_label())
        self.summary_date_label.setStyleSheet("font-size:16px; font-weight:800; color:#6f4832; background:transparent;")

        title_wrap.addWidget(icon)
        title_wrap.addLayout(title_col)
        title_wrap.addStretch()

        date_chip = QFrame()
        date_chip.setStyleSheet("background:transparent; border:none;")
        date_chip_layout = QHBoxLayout(date_chip)
        date_chip_layout.setContentsMargins(0, 0, 0, 0)
        date_chip_layout.addWidget(self.summary_date_label)

        top.addLayout(title_wrap, 1)
        top.addWidget(date_chip, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.summary_receipt_rows = {}
        rows = [
            ("total_orders", "receipt", "Total Orders", "-"),
            ("total_revenue", "coins", "Total Revenue", "-"),
            ("solo_cups", "solo_cup", "Solo Cups Used", "-"),
            ("large_cups", "large_cup", "Large Cups Used", "-"),
            ("top_products", "star", "Top Products", "-"),
            ("low_stock", "warning", "Low Stock Items", "-"),
        ]

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)

        for index, (key, icon_kind, label_text, default_value) in enumerate(rows):
            stat = QFrame()
            stat.setProperty("summaryStat", "true")
            stat_layout = QHBoxLayout(stat)
            stat_layout.setContentsMargins(18, 16, 18, 16)
            stat_layout.setSpacing(18)

            stat_icon = self.summary_icon_badge(icon_kind, 56, 28)

            text_col = QVBoxLayout()
            text_col.setSpacing(6)
            label = QLabel(label_text)
            label.setStyleSheet("font-size:15px; color:#8a7466; background:transparent;")
            value = QLabel(default_value)
            value.setStyleSheet("font-size:22px; font-weight:900; color:#3f2418; background:transparent;")
            value.setWordWrap(True)
            text_col.addWidget(label)
            text_col.addWidget(value)

            stat_layout.addWidget(stat_icon)
            stat_layout.addLayout(text_col, 1)
            grid.addWidget(stat, index // 2, index % 2)
            self.summary_receipt_rows[key] = value

        layout.addLayout(grid)

        receipt_btn = QPushButton("View Full Report")
        receipt_btn.setMinimumHeight(58)
        receipt_btn.setStyleSheet("""
            QPushButton {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9a5e34, stop:1 #7f4b29);
                color:white;
                border:none;
                border-radius:18px;
                padding:18px 20px;
                font-size:16px;
                font-weight:900;
            }
            QPushButton:hover { background:#8a512d; }
        """)
        receipt_btn.clicked.connect(self.handle_quick_view_reports)
        layout.addWidget(receipt_btn)
        return card

    def price_value_from_text(self, price_text):
        raw = str(price_text or "0").replace("\u20b1", "").replace(",", "").strip()
        if "/" in raw:
            raw = raw.split("/", 1)[0].strip()
        try:
            return int(float(raw or 0))
        except Exception:
            return 0

    def normalize_order_category(self, category, product_name=""):
        combined = f"{category} {product_name}".lower()
        if "milkshake" in combined or "shake" in combined or "frappe" in combined:
            return "milkshake"
        if "cream base" in combined or "cookies & cream" in combined or "cookies and cream" in combined or "o-cream" in combined:
            return "cream_base"
        if "fruit" in combined or "avocado" in combined or "mango" in combined or "strawberry" in combined:
            return "fruit"
        if "coffee" in combined or "mocha" in combined or "espresso" in combined or "americano" in combined or "cappuccino" in combined:
            return "iced_coffee"
        return "milk"

    def current_order_slot_label(self):
        current = QDateTime.currentDateTime()
        hour = current.time().hour()
        return self.format_order_slot_label(hour)

    def ensure_order_row(self, slot_label):
        if not hasattr(self, "orders_table"):
            return None

        for row in range(self.order_data_row_count()):
            item = self.orders_table.item(row, 0)
            if item and item.text() == slot_label:
                return row

        row = self.order_data_row_count()
        self.orders_table.blockSignals(True)
        self.orders_table.insertRow(row)

        defaults = [slot_label, "0", "0", "0", "0", "0", "0", "0"]
        for col, value in enumerate(defaults):
            self.orders_table.setItem(row, col, self.create_order_table_item(value, editable=(col not in [0, 6])))

        self.orders_table.blockSignals(False)
        return row

    def add_product_to_orders(self, product, order_config=None):
        self.rollover_order_summary_if_needed()
        if not hasattr(self, "orders_table"):
            orders_builder_name = "page_cashier_orders" if self.is_cashier_role() else "page_orders"
            orders_page_index = self.page_index_by_builder_name(orders_builder_name)
            if orders_page_index is not None:
                self.ensure_stack_page_loaded(orders_page_index)
        if not hasattr(self, "orders_table"):
            self.show_notification("Orders", "Unable to prepare the order window right now.", "warning")
            return
        if not product.get("available", True):
            product_name = str(product.get("name", "Product")).strip() or "Product"
            self.show_notification(
                "Product Unavailable",
                f"{product_name} is currently not available and cannot be ordered.",
                "warning",
                3200
            )
            return
        if not self.can_accept_orders_now():
            self.show_notification(
                "Store Closed",
                "Orders are only allowed from 8:00 AM to 11:00 PM. Monitoring resumes at 8:00 AM.",
                "warning",
                3400
            )
            return

        if order_config is None:
            dialog = OrderCustomizeDialog(self, product)
            if dialog.exec_() != QDialog.Accepted:
                return
            order_config = dialog.order_data()
        order_config = dict(order_config or {})
        order_config.setdefault("cashier_name", self.current_user_name())
        order_config.setdefault("customer_name", order_config.get("customer_name") or "Walk-in Customer")
        order_config.setdefault("order_type", order_config.get("order_type") or "Dine-in")
        order_config.setdefault("payment_method", order_config.get("payment_method") or "Cash")

        slot_label = self.current_order_slot_label()
        row = self.ensure_order_row(slot_label)
        if row is None:
            return

        product_name = str(product.get("name", "Product")).strip() or "Product"
        product_price = self.price_value_from_text(product.get("price_text", "0"))
        quantity = max(1, int(order_config.get("quantity", 1)))
        size = str(order_config.get("size", "Solo")).strip() or "Solo"
        order_total = int(order_config.get("total_price", product_price * quantity))
        user_id = self.current_user_id()
        product_id = product.get("id") or product.get("product_id")
        if not user_id or not product_id:
            self.show_notification("Order Error", "Missing cashier or product database ID.", "error", 3400)
            return

        try:
            db_record = database.create_order_record(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                size_label=size,
                unit_price=int(order_config.get("unit_price", product_price) or product_price),
                total_amount=order_total,
                cash_tendered=int(order_config.get("amount_tendered", order_total) or order_total),
                addon_items=self.build_database_addon_items(order_config),
                status="Pending",
                created_at=QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"),
            )
        except Exception as e:
            self.show_notification("Order Error", f"Could not save order to database:\n{e}", "error", 3600)
            return

        self.orders_table.blockSignals(True)

        category_key = self.normalize_order_category(product.get("category", ""), product_name)
        count_column_map = {
            "milk": 1,
            "fruit": 2,
            "iced_coffee": 3,
            "milkshake": 4,
            "cream_base": 5,
        }
        count_col = count_column_map[category_key]
        count_item = self.orders_table.item(row, count_col)
        if count_item is None:
            count_item = QTableWidgetItem("0")
            count_item.setTextAlignment(Qt.AlignCenter)
            self.orders_table.setItem(row, count_col, count_item)
        count_item.setText(str(self.safe_int(count_item.text()) + quantity))

        revenue_item = self.orders_table.item(row, 7)
        if revenue_item is None:
            revenue_item = QTableWidgetItem("0")
            revenue_item.setTextAlignment(Qt.AlignCenter)
            self.orders_table.setItem(row, 7, revenue_item)
        revenue_item.setText(str(self.safe_int(revenue_item.text()) + order_total))

        total_item = self.orders_table.item(row, 6)
        if total_item is None:
            total_item = QTableWidgetItem("0")
            total_item.setTextAlignment(Qt.AlignCenter)
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self.orders_table.setItem(row, 6, total_item)

        total_orders = (
            self.safe_int(self.orders_table.item(row, 1).text() if self.orders_table.item(row, 1) else 0) +
            self.safe_int(self.orders_table.item(row, 2).text() if self.orders_table.item(row, 2) else 0) +
            self.safe_int(self.orders_table.item(row, 3).text() if self.orders_table.item(row, 3) else 0) +
            self.safe_int(self.orders_table.item(row, 4).text() if self.orders_table.item(row, 4) else 0) +
            self.safe_int(self.orders_table.item(row, 5).text() if self.orders_table.item(row, 5) else 0)
        )
        total_item.setText(str(total_orders))
        self.orders_table.blockSignals(False)

        size_key = "large" if size.strip().lower() == "large" else "solo"
        self.daily_size_counts[size_key] = self.daily_size_counts.get(size_key, 0) + quantity
        self.daily_product_sales[product_name] = self.daily_product_sales.get(product_name, 0) + quantity
        new_entry = self.build_order_entry(product, order_config, slot_label, order_total)
        new_entry["db_order_id"] = db_record.get("order_id")
        new_entry["db_order_item_id"] = db_record.get("order_item_id")
        new_entry["order_code"] = db_record.get("order_code", "")
        self.order_entries.append(new_entry)
        self.add_recent_activity(
            "#95ad72",
            "O",
            "Order completed",
            slot_label,
            activity_type="order_completed",
            product_name=product_name,
            image_path=product.get("image_path") or product.get("image") or "",
        )

        self.refresh_order_summary()
        self.apply_inventory_deduction_for_order(product, order_config)
        self.persist_order_summary_progress()
        self.refresh_connected_views()
        self.show_notification(
            "Added to Order",
            f"{product_name} ({size}) x{quantity} was added to the order summary for {slot_label}.",
            "success",
            3200
        )

    def page_dashboard(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        layout.addWidget(self.page_header("Dashboard", f"Welcome to Best Brew {self.role_display_name()} Dashboard"))

        cards = QGridLayout()
        cards.setSpacing(18)
        cards.addWidget(self.metric_card("Total Products", "6", "☕", "#dfe8f6"), 0, 0)
        cards.addWidget(self.metric_card("Today's Orders", "0", "🛒", "#dff1e1"), 0, 1)
        cards.addWidget(self.metric_card("Total Revenue", "₱270", "₱", "#efe2f7"), 0, 2)
        cards.addWidget(self.metric_card("Low Stock Items", "7", "⚠", "#f5dddd"), 0, 3)
        layout.addLayout(cards)

        lower = QGridLayout()
        lower.setSpacing(18)

        alerts_card, alerts_layout = self.dashboard_panel_card()
        alerts_header_widget, _ = self.dashboard_panel_header("🔔", "Low Stock Alerts")
        alerts_layout.addWidget(alerts_header_widget)
        for title, desc in [
            ("Tapioca Pearls", "Current: 8 kg | Reorder Level: 15 kg"),
            ("Fresh Milk", "Current: 25 liters | Reorder Level: 30 liters"),
            ("Taro Powder", "Current: 7 kg | Reorder Level: 10 kg"),
        ]:
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background:#f4e7da;
                    border:1px solid #ead7c5;
                    border-radius:14px;
                }
            """)
            r = QHBoxLayout(row)
            r.setContentsMargins(16, 14, 16, 14)

            left = QVBoxLayout()
            left.setContentsMargins(0, 0, 0, 0)
            left.setSpacing(4)
            lbl1 = QLabel(title)
            lbl1.setFrameShape(QFrame.NoFrame)
            lbl1.setStyleSheet("font-size:16px; font-weight:800; background:transparent; border:none; padding:0; margin:0;")
            lbl2 = QLabel(desc)
            lbl2.setFrameShape(QFrame.NoFrame)
            lbl2.setStyleSheet("""
                font-size:14px;
                color:#7a6e66;
                background:transparent;
                border:none;
                padding:0;
                margin:0;
            """)
            left.addWidget(lbl1)
            left.addWidget(lbl2)

            badge = QLabel("Low Stock")
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("""
                background:#a8472d;
                color:white;
                border-radius:12px;
                padding:6px 12px;
                font-size:13px;
                font-weight:800;
            """)

            r.addLayout(left)
            r.addStretch()
            r.addWidget(badge)
            alerts_layout.addWidget(row)

        pending_card, pending_layout = self.section_card("Pending Orders")
        pending_text = QLabel("No pending orders")
        pending_text.setAlignment(Qt.AlignCenter)
        pending_text.setStyleSheet("font-size:20px; color:#8a6f61; padding:80px; background:transparent;")
        pending_layout.addWidget(pending_text)

        lower.addWidget(alerts_card, 0, 0)
        lower.addWidget(pending_card, 0, 1)
        layout.addLayout(lower)
        layout.addStretch()

        return self.build_scroll_page(content)

    def page_dashboard_v2(self):
        live = self.collect_live_system_data()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 12, 16, 18)
        layout.setSpacing(10)

        layout.addWidget(self.dashboard_header())

        cards = QGridLayout()
        cards.setSpacing(12)
        cards.addWidget(self.metric_card("Total Products", "6", "☕", "#dfe8f6"), 0, 0)
        cards.addWidget(self.metric_card("Today's Orders", "0", "🛒", "#dff1e1"), 0, 1)
        cards.addWidget(self.metric_card("Total Revenue", "₱270", "₱", "#efe2f7"), 0, 2)
        cards.addWidget(self.metric_card("Low Stock Items", "7", "⚠", "#f5dddd"), 0, 3)
        layout.addLayout(cards)
        self.update_metric_card(cards.itemAtPosition(0, 0).widget(), str(live["total_products"]))
        self.update_metric_card(cards.itemAtPosition(0, 1).widget(), str(live["total_orders"]))
        self.update_metric_card(cards.itemAtPosition(0, 2).widget(), f"₱{live['total_revenue']:,}")
        self.update_metric_card(cards.itemAtPosition(0, 3).widget(), str(live["low_stock_count"]))

        top_row = QGridLayout()
        top_row.setSpacing(8)
        top_row.setColumnStretch(0, 5)
        top_row.setColumnStretch(1, 4)

        sales_card, sales_layout = self.section_card("Sales Overview")
        sales_card.setStyleSheet("""
            QFrame#card {
                background:#fffdfb;
                border:1px solid #efdece;
                border-radius:22px;
            }
        """)
        sales_layout.setContentsMargins(18, 10, 18, 14)
        sales_layout.setSpacing(10)
        sales_top = QHBoxLayout()
        sales_total = QVBoxLayout()
        sales_total.setSpacing(1)
        revenue_label = QLabel("Total Revenue")
        revenue_label.setStyleSheet("font-size:12px; font-weight:700; color:#7f6f65;")
        total_value = QLabel(f"₱{live['total_revenue']:,}")
        total_value.setStyleSheet("font-size:18px; font-weight:900; color:#2b1b14;")
        sales_total.addWidget(revenue_label)
        sales_total.addWidget(total_value)
        sales_delta = QLabel("↑ 15%\nvs last week")
        sales_delta.setStyleSheet("""
            background:#edf4e6;
            color:#86a56a;
            border-radius:12px;
            padding:5px 10px;
            font-size:11px;
            font-weight:800;
        """)
        sales_info = QHBoxLayout()
        sales_info.setSpacing(10)
        sales_info.addLayout(sales_total)
        sales_info.addWidget(sales_delta, 0, Qt.AlignVCenter)
        sales_info.addStretch()
        sales_top.addLayout(sales_info)
        sales_top.addStretch()
        sales_top.addWidget(self.dashboard_filter_chip("This Week"))
        sales_layout.addLayout(sales_top)
        sales_layout.addWidget(RevenueChartWidget(live["revenue_labels"], live["revenue_values"]))
        top_row.addWidget(sales_card, 0, 0)

        inventory_card, inventory_layout = self.section_card("Inventory Status")
        inventory_card.setStyleSheet("""
            QFrame#card {
                background:#fffdfb;
                border:1px solid #efdece;
                border-radius:22px;
            }
        """)
        inventory_card.setMinimumHeight(260)
        inventory_layout.setContentsMargins(18, 16, 18, 18)
        inventory_layout.setSpacing(12)
        inventory_center = QWidget()
        inventory_center.setStyleSheet("background:transparent;")
        inventory_center_layout = QHBoxLayout(inventory_center)
        inventory_center_layout.setContentsMargins(4, 0, 4, 0)
        inventory_center_layout.setSpacing(12)
        inventory_center_layout.setAlignment(Qt.AlignCenter)
        inventory_center_layout.addWidget(DonutChartWidget([
            max(0, live["total_products"] - live["low_stock_count"]),
            live["low_stock_count"],
            0
        ], ["#8ca55a", "#eb9b45", "#d7493b"], center_top=str(live["total_products"]), center_bottom=""))
        legend = QVBoxLayout()
        legend.setSpacing(10)
        legend.setAlignment(Qt.AlignVCenter)
        for color, label, count in [
            ("#8ca55a", "In Stock", str(max(0, live["total_products"] - live["low_stock_count"]))),
            ("#eb9b45", "Low Stock", str(live["low_stock_count"])),
            ("#d7493b", "Out of Stock", "0 (0%)"),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setAlignment(Qt.AlignVCenter)
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background:{color}; border-radius:6px;")
            text = QLabel(label)
            text.setStyleSheet("font-size:16px; font-weight:600; color:#5d4638;")
            count_lbl = QLabel(count)
            count_lbl.setStyleSheet("font-size:16px; font-weight:600; color:#8c796d;")
            row.addWidget(dot)
            row.addWidget(text)
            row.addStretch()
            row.addWidget(count_lbl)
            legend.addLayout(row)
        inventory_center_layout.addLayout(legend, 1)
        inventory_layout.addWidget(inventory_center)
        top_row.addWidget(inventory_card, 0, 1)
        layout.addLayout(top_row)

        middle_row = QGridLayout()
        middle_row.setSpacing(14)
        middle_row.setColumnStretch(0, 4)
        middle_row.setColumnStretch(1, 3)
        middle_row.setColumnStretch(2, 2)

        alerts_card, alerts_layout = self.dashboard_panel_card()
        alerts_header_widget, _ = self.dashboard_panel_header("\U0001F514", "Low Stock Alerts")
        alerts_layout.addWidget(alerts_header_widget)
        for product in live["low_stock_items"][:5]:
            alerts_layout.addWidget(self.dashboard_low_stock_row(product))
        if not live["low_stock_items"]:
            empty_alerts = QLabel("No low stock alerts right now.")
            empty_alerts.setStyleSheet("font-size:14px; color:#8c796d; padding:14px 4px;")
            alerts_layout.addWidget(empty_alerts)
        alerts_layout.addStretch()
        middle_row.addWidget(alerts_card, 0, 0)

        activity_card, activity_layout = self.dashboard_panel_card()
        activity_header_widget, activity_btn = self.dashboard_panel_header("⌁", "Recent Activity", "View All")
        if activity_btn is not None:
            activity_btn.clicked.connect(self.handle_quick_view_reports)
        activity_layout.addWidget(activity_header_widget)
        fallback_activity = {"color": "#d7b094", "icon": "?", "title": "No recent activity yet", "timestamp": "Just now", "activity_type": "generic", "product_name": "", "image_path": ""}
        for activity in (self.recent_activities[-4:] if self.recent_activities else [fallback_activity]):
            if isinstance(activity, dict):
                activity_layout.addWidget(self.dashboard_activity_row(
                    activity.get("color", "#d7b094"),
                    activity.get("icon", "?"),
                    activity.get("title", "Activity"),
                    activity.get("timestamp", "Just now"),
                    activity.get("activity_type", "generic"),
                    activity.get("product_name", ""),
                    activity.get("image_path", ""),
                ))
            else:
                activity_layout.addWidget(self.dashboard_activity_row(*activity))
        activity_layout.addStretch()
        middle_row.addWidget(activity_card, 0, 1)

        top_products_card, top_products_layout = self.dashboard_panel_card()
        top_products_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        top_products_layout.setSpacing(8)
        products_header_widget, _ = self.dashboard_panel_header("☆", "Top Products", "This Month")
        top_products_layout.addWidget(products_header_widget)
        top_products = live["top_products"][:5] or self.dashboard_fallback_top_products(5)
        for product in top_products:
            top_products_layout.addWidget(self.dashboard_product_row(product))
        view_products = QPushButton("View All Products")
        view_products.setCursor(Qt.PointingHandCursor)
        view_products.setStyleSheet("""
            QPushButton {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a94f28, stop:1 #8a3f1f);
                color:white;
                border:none;
                border-radius:14px;
                padding:14px 18px;
                font-size:13px;
                font-weight:900;
            }
            QPushButton:hover { background:#8d4322; }
        """)
        view_products.clicked.connect(
            lambda checked=False: self.handle_quick_new_order() if self.is_cashier_role() else self.switch_to_builder("page_products")
        )
        top_products_layout.addStretch()
        top_products_layout.addWidget(view_products)
        middle_row.addWidget(top_products_card, 0, 2)

        if self.is_cashier_role():
            self.configure_cashier_dashboard_touch_targets(
                cards,
                alerts_layout=alerts_layout,
                activity_layout=activity_layout,
                products_layout=top_products_layout,
            )

        layout.addLayout(middle_row)

        return self.build_scroll_page(content)

    def page_inventory(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 14, 20, 22)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)

        layout.addWidget(self.page_header("Inventory Management", "Track and manage your stock levels"))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        title = QLabel("Inventory Items")
        title.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        toolbar.addWidget(title)

        search = QLineEdit()
        search.setPlaceholderText("Search inventory...")
        search.setStyleSheet("""
            QLineEdit {
                background:#fffaf5;
                border:1px solid #eadacc;
                border-radius:12px;
                padding:13px 16px;
                font-size:15px;
            }
        """)
        toolbar.addSpacing(12)
        toolbar.addWidget(search, 3)
        self.inventory_search_input = search
        self.inventory_search_input.textChanged.connect(self.filter_inventory_rows)

        self.inventory_category_btn = self.inventory_toolbar_chip("All Categories", with_arrow=True)
        self.inventory_status_btn = self.inventory_toolbar_chip("All Status", with_arrow=True)
        self.inventory_add_item_btn = self.inventory_toolbar_chip("+  Add New Item", dark=True)
        self.inventory_category_btn.setFixedWidth(156)
        self.inventory_status_btn.setFixedWidth(118)
        self.inventory_add_item_btn.setFixedWidth(172)
        if self.is_cashier_role():
            self.inventory_add_item_btn.setEnabled(False)
            self.inventory_add_item_btn.setToolTip("Only admins can add inventory items.")

        toolbar.addWidget(self.inventory_category_btn)
        toolbar.addWidget(self.inventory_status_btn)
        toolbar.addWidget(self.inventory_add_item_btn)
        layout.addLayout(toolbar)

        inventory_card = QFrame()
        inventory_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        inventory_card.setStyleSheet("""
            QFrame {
                background:transparent;
                border:none;
            }
        """)
        inventory_layout = QVBoxLayout(inventory_card)
        inventory_layout.setContentsMargins(0, 4, 0, 0)
        inventory_layout.setSpacing(12)
        header_wrap = QFrame()
        header_wrap.setStyleSheet("""
            QFrame {
                background:transparent;
                border:none;
                border-radius:0;
            }
        """)
        header = QHBoxLayout(header_wrap)
        header.setContentsMargins(22, 6, 22, 6)
        header.setSpacing(16)
        for txt, stretch, align in [
            ("Item Name", 3, Qt.AlignLeft),
            ("Category", 2, Qt.AlignLeft),
            ("Current Stock", 2, Qt.AlignLeft),
            ("Reorder Level", 2, Qt.AlignLeft),
            ("Status", 1, Qt.AlignCenter),
            ("Last Restocked", 2, Qt.AlignCenter),
            ("Action", 1, Qt.AlignCenter),
        ]:
            lbl = QLabel(txt)
            lbl.setAlignment(align)
            lbl.setStyleSheet("font-size:15px; font-weight:900; color:#6d5c50; border:none;")
            header.addWidget(lbl, stretch)
        inventory_layout.addWidget(header_wrap)

        divider = QFrame()
        divider.setStyleSheet("background:#efe1d2; min-height:1px; max-height:1px; border:none;")
        inventory_layout.addWidget(divider)

        self.inventory_row_widgets = []

        for item in self.inventory_items:
            line = QFrame()
            line.setStyleSheet("""
                QFrame {
                    background:#fffdfb;
                    border:1px solid #efe0d1;
                    border-radius:20px;
                }
            """)
            row = QHBoxLayout(line)
            row.setContentsMargins(18, 16, 18, 16)
            row.setSpacing(18)

            item_wrap = QHBoxLayout()
            item_wrap.setSpacing(14)
            item_wrap.addWidget(self.inventory_item_icon(item["icon"], item["accent"]))
            name_lbl = QLabel(item["name"])
            name_lbl.setStyleSheet("font-size:16px; font-weight:900; color:#2d1e15;")
            item_wrap.addWidget(name_lbl)
            item_wrap.addStretch()

            row.addLayout(item_wrap, 3)

            row.addWidget(self.inventory_info_chip(item["category"], "category"), 2, Qt.AlignCenter)

            row.addWidget(self.inventory_info_chip(item["stock"], "stock"), 2, Qt.AlignCenter)

            row.addWidget(self.inventory_info_chip(item["reorder"], "reorder"), 2, Qt.AlignCenter)

            row.addWidget(self.inventory_status_badge(item["status"]), 1, Qt.AlignCenter)

            date_lbl = QLabel(item["date"])
            date_lbl.setAlignment(Qt.AlignCenter)
            date_lbl.setStyleSheet("font-size:15px; color:#6d5b50; font-weight:500; background:transparent;")
            row.addWidget(date_lbl, 2)

            btn = QPushButton("🛒 Restock")
            btn.setStyleSheet("""
                QPushButton {
                    background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #cb8d59, stop:1 #b67643);
                    color:white;
                    border:none;
                    border-radius:14px;
                    padding:12px 20px;
                    font-size:14px;
                    font-weight:800;
                }
                QPushButton:hover { background:#a96536; }
            """)
            btn.clicked.connect(
                lambda checked, item_data=item: self.open_restock_dialog(
                    item_data["name"],
                    item_data["stock"],
                    item_data.get("id")
                )
            )
            if self.is_cashier_role():
                btn.setEnabled(False)
                btn.setToolTip("Only admins can restock inventory.")
            row.addWidget(btn, 1)

            inventory_layout.addWidget(line)
            self.inventory_row_widgets.append((line, item))

        self.inventory_category_filter_value = "All Categories"
        self.inventory_status_filter_value = "All Status"

        category_menu = QMenu(self)
        all_category_action = category_menu.addAction("All Categories")
        all_category_action.triggered.connect(lambda checked=False: self.set_inventory_category_filter("All Categories"))
        for category in sorted({item.get("category", "") for item in self.inventory_items if item.get("category")}):
            action = category_menu.addAction(category)
            action.triggered.connect(lambda checked=False, value=category: self.set_inventory_category_filter(value))
        self.inventory_category_btn.setMenu(category_menu)

        status_menu = QMenu(self)
        all_status_action = status_menu.addAction("All Status")
        all_status_action.triggered.connect(lambda checked=False: self.set_inventory_status_filter("All Status"))
        for status in sorted({item.get("status", "") for item in self.inventory_items if item.get("status")}):
            action = status_menu.addAction(status)
            action.triggered.connect(lambda checked=False, value=status: self.set_inventory_status_filter(value))
        self.inventory_status_btn.setMenu(status_menu)

        self.inventory_add_item_btn.clicked.connect(self.handle_add_inventory_item)
        self.filter_inventory_rows()

        layout.addWidget(inventory_card)
        return self.build_scroll_page(content)

    def page_orders(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(20)

        layout.addWidget(self.page_header("Order Summary", "Hourly monitoring sheet with receipt-style daily summary"))

        self.order_summary_grid = QGridLayout()
        self.order_summary_grid.setSpacing(18)

        self.card_total_slots = self.metric_card("Total Time Slots", "0", "🕒", "#f8eee4")
        self.card_total_logged = self.metric_card("Total Orders Logged", "0", "🧾", "#dfe8f6")
        self.card_total_revenue = self.metric_card("Total Revenue", "₱0", "₱", "#efe2f7")
        self.card_most_active = self.metric_card("Most Active Slot", "-", "★", "#dff1e1")

        self.order_summary_grid.addWidget(self.card_total_slots, 0, 0)
        self.order_summary_grid.addWidget(self.card_total_logged, 0, 1)
        self.order_summary_grid.addWidget(self.card_total_revenue, 0, 2)
        self.order_summary_grid.addWidget(self.card_most_active, 0, 3)
        layout.addLayout(self.order_summary_grid)

        orders_card, orders_layout = self.section_card("Daily Order Monitoring Sheet")
        orders_card.setStyleSheet("""
            QFrame#card {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255, 252, 248, 0.99), stop:1 rgba(247, 241, 255, 0.99));
                border:1px solid #eaded5;
                border-radius:22px;
            }
        """)

        date_row = QHBoxLayout()
        self.orders_date_label = QLabel(f"DATE: {self.active_summary_date_label()}")
        self.orders_date_label.setStyleSheet("font-size:15px; font-weight:900; color:#744b34; background:transparent;")
        note_lbl = QLabel("Hourly counts update the day summary automatically.")
        note_lbl.setStyleSheet("font-size:13px; color:#7d7068; background:transparent;")
        date_row.addWidget(self.orders_date_label)
        date_row.addStretch()
        date_row.addWidget(note_lbl)
        orders_layout.addLayout(date_row)

        self.orders_table = QTableWidget()
        self.orders_table.setRowCount(len(self.order_rows) + 1)
        self.orders_table.setColumnCount(8)
        self.orders_table.setHorizontalHeaderLabels([
            "Time Slot",
            "Milk Tea",
            "Fruit Tea",
            "Iced Coffee",
            "Milkshake",
            "Cream Base",
            "Total Orders",
            "Revenue (₱)"
        ])

        self.orders_table.setStyleSheet("""
            QTableWidget {
                background:#fffdf9;
                border:1px solid #e8ddd6;
                border-radius:18px;
                gridline-color:#eee5df;
                font-size:16px;
                color:#3a2b24;
                selection-background-color:#f7e7dd;
                selection-color:#2a1a12;
                alternate-background-color:#fffaf5;
            }
            QHeaderView::section {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8efe4, stop:1 #efe1d1);
                color:#6f4d37;
                border:none;
                border-right:1px solid #ece2db;
                border-bottom:1px solid #ece2db;
                padding:18px 12px;
                font-size:15px;
                font-weight:900;
            }
            QTableWidget::item {
                padding:16px 12px;
            }
        """)
        self.orders_table.verticalHeader().setVisible(False)
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.orders_table.setShowGrid(True)
        self.orders_table.verticalHeader().setDefaultSectionSize(54)

        header = self.orders_table.horizontalHeader()
        header.setMinimumSectionSize(92)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        self.orders_table.setColumnWidth(0, 250)
        for col in range(1, 6):
            self.orders_table.setColumnWidth(col, 135)
        self.orders_table.setColumnWidth(6, 130)
        self.orders_table.setColumnWidth(7, 170)

        for row_idx, row_data in enumerate(self.order_rows):
            for col_idx, value in enumerate(row_data):
                self.orders_table.setItem(row_idx, col_idx, self.create_order_table_item(value, editable=(col_idx not in [0, 6])))

        self.initialize_orders_footer_row()

        self.orders_table.setMinimumHeight(760)
        self.orders_table.itemChanged.connect(self.recompute_order_table)
        orders_layout.addWidget(self.orders_table)

        self.totals_grid_host = QWidget()
        self.totals_grid_host.setVisible(False)
        self.totals_grid = QGridLayout(self.totals_grid_host)

        hours_title = QLabel(f"Shop Operating Hours: {self.store_hours_label()}")
        hours_title.setStyleSheet("font-size:14px; font-weight:900; color:#8b5638;")
        hours_sub = QLabel("Data is automatically summarized from the current monitoring sheet.")
        hours_sub.setStyleSheet("font-size:12px; color:#8d7c70;")
        layout.addWidget(hours_title)
        layout.addWidget(hours_sub)
        layout.addWidget(orders_card)

        self.order_status_card, order_status_layout = self.section_card("Today's Order Status")
        self.order_status_card.setStyleSheet("""
            QFrame#card {
                background:#fffaf5;
                border:1px solid #eadacd;
                border-radius:20px;
            }
        """)
        if self.is_cashier_role():
            status_note_text = "Every new order starts as Pending. Change the dropdown below when the order is already being prepared or completed."
        else:
            status_note_text = "Cashier manages the order status. Admin can monitor the latest status updates here in real time."
        status_note = QLabel(status_note_text)
        status_note.setStyleSheet("font-size:13px; color:#7d7068;")
        order_status_layout.addWidget(status_note)

        self.order_entries_table = QTableWidget()
        if self.is_cashier_role():
            self.order_entries_table.setColumnCount(8)
            self.order_entries_table.setHorizontalHeaderLabels([
                "Order No.",
                "Time",
                "Product",
                "Size",
                "Qty",
                "Total",
                "Status",
                "Action",
            ])
        else:
            self.order_entries_table.setColumnCount(7)
            self.order_entries_table.setHorizontalHeaderLabels([
                "Order No.",
                "Time",
                "Product",
                "Size",
                "Qty",
                "Total",
                "Status",
            ])
        self.order_entries_table.setStyleSheet("""
            QTableWidget {
                background:#fffdf9;
                border:1px solid #e8ddd6;
                border-radius:18px;
                gridline-color:#eee5df;
                font-size:15px;
                color:#3a2b24;
                selection-background-color:#f7e7dd;
                selection-color:#2a1a12;
                alternate-background-color:#fffaf5;
            }
            QHeaderView::section {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8efe4, stop:1 #efe1d1);
                color:#6f4d37;
                border:none;
                border-right:1px solid #ece2db;
                border-bottom:1px solid #ece2db;
                padding:14px 10px;
                font-size:14px;
                font-weight:900;
            }
        """)
        self.order_entries_table.verticalHeader().setVisible(False)
        self.order_entries_table.setAlternatingRowColors(True)
        self.order_entries_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_entries_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.order_entries_table.setMinimumHeight(320)
        self.order_entries_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.order_entries_table.setColumnWidth(0, 170)
        self.order_entries_table.setColumnWidth(1, 110)
        self.order_entries_table.setColumnWidth(2, 250)
        self.order_entries_table.setColumnWidth(3, 90)
        self.order_entries_table.setColumnWidth(4, 80)
        self.order_entries_table.setColumnWidth(5, 110)
        self.order_entries_table.setColumnWidth(6, 150)
        if self.is_cashier_role():
            self.order_entries_table.setColumnWidth(7, 140)
        order_status_layout.addWidget(self.order_entries_table)
        layout.addWidget(self.order_status_card)

        self.totals_card = self.build_summary_receipt_v2()
        layout.addWidget(self.totals_card)

        page = self.build_scroll_page(content)
        self.refresh_order_summary()
        return page

    def refresh_order_entries_table(self):
        self.rollover_order_summary_if_needed()
        self.migrate_misaligned_current_entries()
        if not hasattr(self, "order_entries_table"):
            return

        entries = list(getattr(self, "order_entries", []))
        self.order_entries_table.blockSignals(True)
        self.order_entries_table.setRowCount(len(entries) if entries else 1)

        if not entries:
            for col in range(self.order_entries_table.columnCount()):
                empty_item = self.create_order_table_item("" if col else "No order records yet", editable=False)
                self.order_entries_table.setItem(0, col, empty_item)
            self.order_entries_table.blockSignals(False)
            return

        for row, entry in enumerate(entries):
            values = [
                entry.get("id", "-"),
                entry.get("display_time", "-"),
                entry.get("product_name", "-"),
                entry.get("size", "-"),
                str(entry.get("quantity", 0)),
                f"₱{self.safe_int(entry.get('total_price', 0)):,}",
            ]
            for col, value in enumerate(values):
                self.order_entries_table.setItem(row, col, self.create_order_table_item(value, editable=False))

            status_value = self.normalize_order_status(entry.get("status"))
            if self.is_cashier_role():
                combo = QComboBox()
                combo.addItems(["Pending", "Processing", "Completed"])
                combo.setCurrentText(status_value)
                combo.setStyleSheet("""
                    QComboBox {
                        background:#fff7ef;
                        border:1px solid #dfc2ab;
                        border-radius:10px;
                        padding:8px 10px;
                        font-size:13px;
                    }
                """)
                combo.currentTextChanged.connect(
                    lambda value, order_id=entry.get("id"): self.update_order_entry_status(order_id, value)
                )
                self.order_entries_table.setCellWidget(row, 6, combo)
            else:
                status_item = self.create_order_table_item(status_value, editable=False)
                status_item.setTextAlignment(Qt.AlignCenter)
                self.order_entries_table.setItem(row, 6, status_item)

            if self.is_cashier_role():
                cancel_btn = QPushButton("Cancel")
                cancel_btn.setCursor(Qt.PointingHandCursor)
                cancel_btn.setStyleSheet("""
                    QPushButton {
                        background:#fff7f0;
                        color:#9b5038;
                        border:1px solid #e4c3b0;
                        border-radius:12px;
                        padding:8px 12px;
                        font-size:13px;
                        font-weight:900;
                    }
                    QPushButton:hover { background:#fbe9de; }
                """)
                cancel_btn.clicked.connect(lambda checked=False, order_id=entry.get("id"): self.cancel_order_entry(order_id))
                self.order_entries_table.setCellWidget(row, 7, cancel_btn)

        self.order_entries_table.blockSignals(False)

    def recompute_order_table(self, item):
        if not item:
            return
        row = item.row()
        if row >= self.order_data_row_count():
            return

        milk = self.safe_int(self.orders_table.item(row, 1).text() if self.orders_table.item(row, 1) else 0)
        fruit = self.safe_int(self.orders_table.item(row, 2).text() if self.orders_table.item(row, 2) else 0)
        iced_coffee = self.safe_int(self.orders_table.item(row, 3).text() if self.orders_table.item(row, 3) else 0)
        milkshake = self.safe_int(self.orders_table.item(row, 4).text() if self.orders_table.item(row, 4) else 0)
        cream_base = self.safe_int(self.orders_table.item(row, 5).text() if self.orders_table.item(row, 5) else 0)

        total_orders = milk + fruit + iced_coffee + milkshake + cream_base

        self.orders_table.blockSignals(True)
        total_item = self.orders_table.item(row, 6)
        if total_item is None:
            total_item = QTableWidgetItem()
            total_item.setTextAlignment(Qt.AlignCenter)
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            self.orders_table.setItem(row, 6, total_item)
        total_item.setText(str(total_orders))
        self.orders_table.blockSignals(False)

        self.refresh_order_summary()

    def refresh_order_summary(self):
        self.rollover_order_summary_if_needed()
        self.migrate_misaligned_current_entries()
        if hasattr(self, "orders_date_label"):
            self.orders_date_label.setText(f"DATE: {self.active_summary_date_label()}")
        if hasattr(self, "summary_date_label"):
            self.summary_date_label.setText(self.active_summary_date_label())

        total_slots = self.order_data_row_count()
        total_orders = 0
        total_revenue = 0
        most_active_slot = "-"
        highest_orders = -1

        milk_total = 0
        fruit_total = 0
        iced_coffee_total = 0
        milkshake_total = 0
        cream_base_total = 0
        coffee_total = 0
        low_stock_total = 0

        for row in range(self.order_data_row_count()):
            slot = self.orders_table.item(row, 0).text() if self.orders_table.item(row, 0) else "-"
            milk = self.safe_int(self.orders_table.item(row, 1).text() if self.orders_table.item(row, 1) else 0)
            fruit = self.safe_int(self.orders_table.item(row, 2).text() if self.orders_table.item(row, 2) else 0)
            iced_coffee = self.safe_int(self.orders_table.item(row, 3).text() if self.orders_table.item(row, 3) else 0)
            milkshake = self.safe_int(self.orders_table.item(row, 4).text() if self.orders_table.item(row, 4) else 0)
            cream_base = self.safe_int(self.orders_table.item(row, 5).text() if self.orders_table.item(row, 5) else 0)
            row_total = self.safe_int(self.orders_table.item(row, 6).text() if self.orders_table.item(row, 6) else 0)
            revenue = self.safe_int(self.orders_table.item(row, 7).text() if self.orders_table.item(row, 7) else 0)

            milk_total += milk
            fruit_total += fruit
            iced_coffee_total += iced_coffee
            coffee_total += iced_coffee
            milkshake_total += milkshake
            cream_base_total += cream_base
            total_orders += row_total
            total_revenue += revenue

            if row_total > highest_orders:
                highest_orders = row_total
                most_active_slot = slot

        for inventory_item in getattr(self, "inventory_items", []):
            if str(inventory_item.get("status", "")).strip().lower() in {"low", "out"}:
                low_stock_total += 1

        self.update_metric_card(self.card_total_slots, str(total_slots))
        self.update_metric_card(self.card_total_logged, str(total_orders))
        self.update_metric_card(self.card_total_revenue, f"₱{total_revenue:,}")
        self.update_metric_card(self.card_most_active, most_active_slot)
        self.update_orders_footer_row(
            milk_total,
            fruit_total,
            iced_coffee_total,
            milkshake_total,
            cream_base_total,
            total_orders,
            total_revenue
        )

        while self.totals_grid.count():
            item = self.totals_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        totals_data = [
            ("Milk Tea Total", str(milk_total)),
            ("Fruit Tea Total", str(fruit_total)),
            ("Coffee Total", str(coffee_total)),
            ("Top Active Slot", str(most_active_slot)),
            ("Low Stock Items", str(low_stock_total)),
            ("Grand Total Orders", str(total_orders)),
            ("Grand Total Revenue", f"₱{total_revenue:,}"),
        ]

        for i, (label, value) in enumerate(totals_data):
            box = QFrame()
            box.setProperty("variant", "dailyBreakdownItem")
            box.setStyleSheet("""
                QFrame[variant="dailyBreakdownItem"] {
                    background:#fdf7f1;
                    border:1px solid #ecdccd;
                    border-radius:14px;
                }
            """)
            b = QVBoxLayout(box)
            b.setContentsMargins(14, 12, 14, 12)
            b.setSpacing(4)
            a = QLabel(label)
            a.setStyleSheet("font-size:13px; color:#7b6e66; background:transparent;")
            c = QLabel(value)
            c.setStyleSheet("font-size:20px; font-weight:900; color:#241610; background:transparent;")
            b.addWidget(a)
            b.addWidget(c)
            self.totals_grid.addWidget(box, i // 2, i % 2)

        top_products = sorted(self.daily_product_sales.items(), key=lambda item: (-item[1], item[0]))
        top_product_text = ", ".join([f"{name} ({count})" for name, count in top_products[:3]]) if top_products else "No top products yet"

        self.update_summary_receipt_row("total_orders", str(total_orders))
        self.update_summary_receipt_row("total_revenue", f"₱{total_revenue:,}")
        self.update_summary_receipt_row("solo_cups", str(self.daily_size_counts.get("solo", 0)))
        self.update_summary_receipt_row("large_cups", str(self.daily_size_counts.get("large", 0)))
        self.update_summary_receipt_row("top_products", top_product_text)
        self.update_summary_receipt_row("low_stock", str(low_stock_total))
        self.refresh_order_entries_table()

    def update_metric_card(self, card, new_value):
        value_label = card.findChild(QLabel, "metricValue")
        if value_label:
            value_label.setText(new_value)

    def page_products(self):
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.products_layout_root = QVBoxLayout(content)
        self.products_layout_root.setContentsMargins(28, 22, 28, 22)
        self.products_layout_root.setSpacing(16)

        header = QWidget()
        header.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(20)

        title_wrap = QWidget()
        title_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        title_col = QVBoxLayout(title_wrap)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(6)
        title = QLabel("Product Management")
        title.setStyleSheet("font-size:26px; font-weight:900; color:#20150f;")
        subtitle = QLabel("Manage your menu items")
        subtitle.setStyleSheet("font-size:14px; color:#8c796d;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        add_btn = None
        if not self.is_cashier_role():
            add_btn = QPushButton("+  Add Product")
            add_btn.setMinimumHeight(46)
            add_btn.setMinimumWidth(150)
            add_btn.setStyleSheet("""
                QPushButton {
                    background:#4a2b1e;
                    color:white;
                    border:none;
                    border-radius:12px;
                    padding:10px 18px;
                    font-size:14px;
                    font-weight:800;
                }
                QPushButton:hover { background:#5b3525; }
            """)
            add_btn.clicked.connect(self.open_add_product)

        filter_wrap = QWidget()
        filter_wrap.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        filter_row = QHBoxLayout(filter_wrap)
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(12)

        self.product_search_input = QLineEdit()
        self.product_search_input.setPlaceholderText("Search product...")
        self.product_search_input.setMinimumHeight(44)
        self.product_search_input.setMinimumWidth(260)
        self.product_search_input.setStyleSheet("""
            QLineEdit {
                background:#fffdfa;
                border:1px solid #ead9c9;
                border-radius:12px;
                padding:0 14px;
                font-size:15px;
                color:#3a281d;
            }
        """)
        self.product_search_input.textChanged.connect(lambda _text: self.schedule_refresh_products_ui(140))

        self.product_category_filter = QComboBox()
        self.product_category_filter.setMinimumHeight(44)
        self.product_category_filter.setMinimumWidth(190)
        self.product_category_filter.setStyleSheet("""
            QComboBox {
                background:#fffdfa;
                border:1px solid #ead9c9;
                border-radius:12px;
                padding:0 14px;
                font-size:15px;
                color:#3a281d;
            }
            QComboBox::drop-down {
                border:none;
                width:28px;
            }
        """)
        categories = sorted({product.get("category", "Classic") for product in self.products if product.get("category")})
        self.product_category_filter.addItem("All Categories")
        self.product_category_filter.addItems(categories)
        self.product_category_filter.currentIndexChanged.connect(lambda _index: self.schedule_refresh_products_ui(80))

        self.product_grid_btn = QPushButton("▦")
        self.product_grid_btn.setFixedSize(44, 44)
        self.product_grid_btn.setStyleSheet("""
            QPushButton {
                background:#b77746;
                color:white;
                border:none;
                border-radius:12px;
                font-size:18px;
                font-weight:900;
            }
        """)

        self.product_list_btn = QPushButton("☰")
        self.product_list_btn.setFixedSize(44, 44)
        self.product_list_btn.setStyleSheet("""
            QPushButton {
                background:#fffdfa;
                color:#8c6c57;
                border:1px solid #ead9c9;
                border-radius:12px;
                font-size:16px;
                font-weight:900;
            }
        """)

        filter_row.addWidget(self.product_search_input)
        filter_row.addWidget(self.product_category_filter)

        top_row.addWidget(title_wrap, 1, Qt.AlignTop)
        top_row.addWidget(filter_wrap, 0, Qt.AlignTop | Qt.AlignRight)

        header_layout.addLayout(top_row)
        if add_btn is not None:
            header_layout.addWidget(add_btn, 0, Qt.AlignLeft)
        self.products_layout_root.addWidget(header)

        self.products_card, self.products_card_layout = self.section_card(f"Products ({len(self.products)})")
        self.products_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.products_card.setStyleSheet("""
            QFrame#card {
                background:#fffaf4;
                border:1px solid #edd9c7;
                border-radius:18px;
            }
        """)
        self.products_grid = QGridLayout()
        self.products_grid.setHorizontalSpacing(18)
        self.products_grid.setVerticalSpacing(20)
        self.products_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.products_card_layout.addLayout(self.products_grid)
        self.products_card_layout.addStretch(1)
        self.products_layout_root.addWidget(self.products_card, 0, Qt.AlignTop)
        self.products_layout_root.addStretch(1)

        self.refresh_products_ui()
        self.products_page_scroll = self.build_scroll_page(content)
        QTimer.singleShot(0, self.refresh_products_ui)
        return self.products_page_scroll

    def refresh_products_ui(self):
        if not hasattr(self, "products_grid"):
            return
        self.refresh_product_filter_options()

        while self.products_grid.count():
            item = self.products_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        visible_products = self.filtered_products()
        self.update_products_section_title()
        available_width = 0
        if hasattr(self, "products_page_scroll") and self.products_page_scroll is not None:
            available_width = self.products_page_scroll.viewport().width() - 72
        if available_width <= 0 and hasattr(self, "products_card") and self.products_card is not None:
            available_width = self.products_card.contentsRect().width() - 24
        if available_width <= 0:
            available_width = max(1180, self.width() - 140)

        gap = self.products_grid.horizontalSpacing() or 18
        min_card_width = 236
        max_columns = min(6, max(1, len(visible_products) or 1))
        columns = max(1, min(max_columns, (available_width + gap) // (min_card_width + gap)))
        card_width = max(min_card_width, int((available_width - (gap * max(0, columns - 1))) / max(columns, 1)))
        card_width = min(card_width, 290)
        image_width = max(188, card_width - 32)

        for idx in range(8):
            self.products_grid.setColumnStretch(idx, 0)
        for idx in range(columns):
            self.products_grid.setColumnStretch(idx, 1)

        for i, product in enumerate(visible_products):
            box = QFrame()
            box.setStyleSheet("""
                QFrame {
                    background:#fffdfa;
                    border:1px solid #ecd8c5;
                    border-radius:18px;
                }
            """)
            box.setFixedWidth(card_width)
            box.setFixedHeight(378)
            box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            v = QVBoxLayout(box)
            v.setContentsMargins(16, 16, 16, 16)
            v.setSpacing(12)

            img = self.product_image_label(product.get("image", ""))
            rendered_img = self.render_product_image(
                product.get("image", ""),
                QSize(image_width, 148),
                self.product_image_background(product.get("category", ""))
            )
            if rendered_img:
                img.setPixmap(rendered_img)
            img.setFixedHeight(148)

            badges = QHBoxLayout()
            badges.setContentsMargins(0, 0, 0, 0)
            badges.setSpacing(6)
            badges.addWidget(self.product_category_badge(product.get("category", "Classic")))
            badges.addStretch()
            badges.addWidget(self.product_status_badge(product.get("available", True)))

            title = QLabel(product["name"])
            title.setWordWrap(True)
            title.setStyleSheet("font-size:16px; font-weight:900; color:#21150f; background:transparent; border:none;")

            product_desc = str(product.get("desc", "")).strip()

            price_lbl = QLabel(f"₱{product['price_text']}")
            price_lbl.setStyleSheet("font-size:17px; font-weight:900; color:#c0602a; background:transparent; border:none;")
            price_lbl.setText(f"\u20b1{product['price_text']}")

            add_btn = None
            if self.is_cashier_role():
                add_btn = self.product_action_button("+ Add to Order", primary=True)
                add_btn.clicked.connect(lambda checked, p=product: self.add_product_to_orders(p))

            btns = QHBoxLayout()
            btns.setSpacing(8)
            edit_btn = self.product_action_button("✎  Edit", primary=True)
            edit_btn.clicked.connect(lambda checked, p=product: self.open_edit_product(p))

            del_btn = self.product_action_button("🗑  Delete", primary=False)
            del_btn.clicked.connect(lambda checked, p=product: self.delete_product(p))
            if self.is_cashier_role():
                edit_btn.hide()
                del_btn.hide()

            btns.addWidget(edit_btn, 1)
            btns.addWidget(del_btn, 1)

            v.addWidget(img)
            v.addLayout(badges)
            v.addWidget(title)
            if product_desc and product_desc.lower() != "no description":
                desc_lbl = QLabel(product_desc)
                desc_lbl.setWordWrap(True)
                desc_lbl.setMaximumHeight(34)
                desc_lbl.setStyleSheet("font-size:12px; color:#7a675b; background:transparent; border:none;")
                v.addWidget(desc_lbl)
            v.addWidget(price_lbl)
            if add_btn is not None:
                v.addWidget(add_btn)
            v.addLayout(btns)

            self.products_grid.addWidget(box, i // columns, i % columns)

    def open_edit_user_dialog(self, user):
        dialog = UserEditDialog(self, user)
        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            updated_user = self.controller.update_user_profile(user.get("user_id"), dialog.form_data())
            if updated_user and str(updated_user.get("username", "")).strip() == str((self.user or {}).get("username", "")).strip():
                self.user = updated_user
                self.refresh_user_identity_labels()
            self.refresh_connected_views(include_products=False)
            self.refresh_users_page_if_visible()
            self.show_notification("User Updated", "User details saved successfully.", "success")
        except Exception as e:
            self.show_notification("Save Error", f"Cannot update user:\n{e}", "error", 3400)

    def page_users(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignTop)

        users = self.load_users_from_database()
        layout.addWidget(self.page_header("Users", "Manage account names, roles, and active status"))

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background:#fffaf4;
                border:1px solid #edd9c7;
                border-radius:18px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(12)

        summary = QLabel(f"{len(users)} account(s) found")
        summary.setStyleSheet("font-size:18px; font-weight:900; color:#7a5a48;")
        card_layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setRowCount(len(users))
        table.setHorizontalHeaderLabels(["ID", "Username", "Full Name", "Role", "Status", "Actions"])
        table.setStyleSheet("""
            QTableWidget {
                background:transparent;
                border:none;
                gridline-color:#f0e4da;
                color:#2e1d14;
                font-size:15px;
                font-weight:700;
                selection-background-color:#f7ebdf;
                alternate-background-color:#fffaf5;
            }
            QHeaderView::section {
                background:#fffaf4;
                color:#6f5646;
                border:none;
                border-bottom:1px solid #eee1d6;
                padding:16px 12px;
                font-size:15px;
                font-weight:900;
            }
        """)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        table.setColumnWidth(0, 70)
        table.verticalHeader().setDefaultSectionSize(60)

        for row, user in enumerate(users):
            values = [
                str(user.get("user_id", "")),
                str(user.get("username", "")),
                str(user.get("full_name", "")),
                str(user.get("role", "")),
                "Active" if int(user.get("is_active", 1) or 0) == 1 else "Inactive",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if col in {0, 3, 4} else Qt.AlignLeft))
                item.setFont(table.font())
                table.setItem(row, col, item)

            action_btn = QPushButton("Edit")
            action_btn.setCursor(Qt.PointingHandCursor)
            action_btn.setStyleSheet("""
                QPushButton {
                    background:#fffdfa;
                    color:#7b4d32;
                    border:1px solid #dfc2ab;
                    border-radius:14px;
                    padding:10px 16px;
                    font-size:15px;
                    font-weight:900;
                }
                QPushButton:hover { background:#f8eee5; }
            """)
            action_btn.clicked.connect(lambda checked=False, item=dict(user): self.open_edit_user_dialog(item))
            table.setCellWidget(row, 5, action_btn)

        card_layout.addWidget(table)
        layout.addWidget(card)
        return self.build_scroll_page(content)

    def page_analytics(self):
        live = self.collect_live_system_data()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 0, 20, 12)
        layout.setSpacing(0)

        export_btn = self.inventory_toolbar_chip("Export Report", with_arrow=True)
        export_btn.clicked.connect(self.export_order_summary_doc)
        layout.addWidget(self.analytics_header(action_widget=export_btn))

        cards = QGridLayout()
        cards.setSpacing(12)
        cards.addWidget(self.analytics_metric_card("Total Products", str(live["total_products"]), "All products in inventory", "☕", "#8d6545", "#6e4b35"), 0, 0)
        cards.addWidget(self.analytics_metric_card("Today's Orders", str(live["total_orders"]), "Orders placed today", "◼", "#c78637", "#a8641f"), 0, 1)
        cards.addWidget(self.analytics_metric_card("Total Revenue", f"₱{live['total_revenue']:,}", "Total sales amount", "₱", "#f1992d", "#d86c17"), 0, 2)
        cards.addWidget(self.analytics_metric_card("Low Stock Items", str(live["low_stock_count"]), "Items running low", "▲", "#d26a4a", "#b6442e"), 0, 3)
        analytics_shell = QFrame()
        analytics_shell.setObjectName("analyticsShell")
        analytics_shell.setStyleSheet("""
            QFrame#analyticsShell {
                background:qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fffaf5, stop:0.6 #fff7f0, stop:1 #f7e7d7);
                border:1px solid #f0dfd0;
                border-radius:28px;
            }
        """)
        analytics_shell_layout = QVBoxLayout(analytics_shell)
        analytics_shell_layout.setContentsMargins(18, 4, 18, 16)
        analytics_shell_layout.setSpacing(10)
        analytics_shell_layout.addLayout(cards)

        upper = QGridLayout()
        upper.setSpacing(14)
        upper.setColumnStretch(0, 5)
        upper.setColumnStretch(1, 4)

        revenue_card = QFrame()
        revenue_card.setObjectName("analyticsRevenueCard")
        revenue_card.setStyleSheet("""
            QFrame#analyticsRevenueCard {
                background:rgba(255, 252, 248, 0.97);
                border:1px solid #ecdccd;
                border-radius:22px;
            }
        """)
        revenue_layout = QVBoxLayout(revenue_card)
        revenue_layout.setContentsMargins(18, 14, 18, 16)
        revenue_layout.setSpacing(12)
        revenue_top = QHBoxLayout()
        revenue_title = QLabel("Daily Revenue (Last 7 Days)")
        revenue_title.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        revenue_top.addWidget(revenue_title)
        revenue_top.addStretch()
        revenue_top.addWidget(self.inventory_toolbar_chip("Last 7 Days", with_arrow=True))
        revenue_layout.addLayout(revenue_top)
        revenue_layout.addWidget(RevenueChartWidget(live["revenue_labels"], live["revenue_values"]))
        upper.addWidget(revenue_card, 0, 0)

        status_card = QFrame()
        status_card.setObjectName("analyticsStatusCard")
        status_card.setStyleSheet("""
            QFrame#analyticsStatusCard {
                background:rgba(255, 252, 248, 0.97);
                border:1px solid #ecdccd;
                border-radius:22px;
            }
        """)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 14, 18, 16)
        status_layout.setSpacing(12)
        status_title = QLabel("Order Status Distribution")
        status_title.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        status_layout.addWidget(status_title)
        status_center = QHBoxLayout()
        status_center.setSpacing(16)
        status_center.addWidget(DonutChartWidget(live["donut_values"], ["#76b255", "#f0aa2b", "#a87543"], center_top=str(live["total_orders"]), center_bottom=""))
        legend = QVBoxLayout()
        legend.setSpacing(12)
        for entry in live["analytics_status"]:
            legend.addWidget(self.analytics_status_row(*entry))
        status_center.addLayout(legend, 1)
        status_layout.addLayout(status_center)
        upper.addWidget(status_card, 0, 1)

        analytics_shell_layout.addLayout(upper)

        perf_card = QFrame()
        perf_card.setObjectName("analyticsPerformanceCard")
        perf_card.setStyleSheet("""
            QFrame#analyticsPerformanceCard {
                background:rgba(255, 252, 248, 0.97);
                border:1px solid #ecdccd;
                border-radius:22px;
            }
        """)
        perf_layout = QVBoxLayout(perf_card)
        perf_layout.setContentsMargins(18, 14, 18, 16)
        perf_layout.setSpacing(12)
        perf_top = QHBoxLayout()
        perf_title = QLabel("Product Performance")
        perf_title.setStyleSheet("font-size:16px; font-weight:900; color:#2b1b14;")
        perf_top.addWidget(perf_title)
        perf_top.addStretch()
        perf_top.addWidget(self.inventory_toolbar_chip("Revenue", with_arrow=True))
        perf_top.addWidget(self.inventory_toolbar_chip("Last 7 Days", with_arrow=True))
        perf_layout.addLayout(perf_top)
        perf_layout.addWidget(ProductBarChartWidget(live["top_products"][:6]))

        analytics_shell_layout.addWidget(perf_card)
        layout.addWidget(analytics_shell)

        return self.build_scroll_page(content)

    def open_add_product(self):
        if self.is_cashier_role():
            self.show_notification("Access Denied", "Only admins can add products.", "warning", 2400)
            return
        dlg = AddEditProductDialog(self)
        if dlg.exec_():
            try:
                dlg.set_submit_state(True)
                self.begin_busy_feedback("Saving Product", "Adding the new product to your menu...")
                portable_image = import_product_image(dlg.image_path)
                self.controller.create_product({
                    "name": dlg.name_input.text().strip(),
                    "category": dlg.category_input.text().strip(),
                    "price_text": dlg.price_input.text().strip(),
                    "desc": "No description",
                    "image": portable_image,
                    "available": dlg.available_input.currentText() == "Available",
                })
                self.clear_product_image_caches()
                self.persist_products()
                self.add_recent_activity("#8d6545", "☕", f"Added product: {dlg.name_input.text().strip()}")
                self.update_products_section_title()
                self.refresh_products_ui()
                self.refresh_connected_views(include_products=True)
                self.show_notification("Product Added", "Product saved successfully.", "success")
            except Exception as e:
                self.show_notification("Save Error", f"Cannot save product:\n{e}", "error", 3400)
            finally:
                self.end_busy_feedback()
                dlg.set_submit_state(False)

    def open_edit_product(self, product):
        dlg = AddEditProductDialog(self, product=product)
        if dlg.exec_():
            try:
                dlg.set_submit_state(True)
                self.begin_busy_feedback("Updating Product", "Saving your product changes...")
                portable_image = import_product_image(dlg.image_path)
                self.controller.update_product(product["id"], {
                    "name": dlg.name_input.text().strip() or product["name"],
                    "category": dlg.category_input.text().strip() or product["category"],
                    "price_text": dlg.price_input.text().strip() or product["price_text"],
                    "desc": product.get("desc", "No description"),
                    "image": portable_image,
                    "available": dlg.available_input.currentText() == "Available",
                })
                self.clear_product_image_caches()
                self.persist_products()
                self.add_recent_activity("#7d5ac7", "✎", f"Updated product: {dlg.name_input.text().strip() or product['name']}")
                self.update_products_section_title()
                self.refresh_products_ui()
                self.refresh_connected_views(include_products=True)
                self.show_notification("Product Updated", "Product updated successfully.", "success")
            except Exception as e:
                self.show_notification("Save Error", f"Cannot update product:\n{e}", "error", 3400)
            finally:
                self.end_busy_feedback()
                dlg.set_submit_state(False)

    def delete_product(self, product):
        dialog = ConfirmActionDialog(
            self,
            title="Delete Product",
            message=f"Delete {product['name']}?",
            confirm_text="Yes",
            cancel_text="No",
        )
        if dialog.exec_() == QDialog.Accepted:
            try:
                self.controller.delete_product(product["id"])
                self.clear_product_image_caches()
                self.persist_products()
                self.add_recent_activity("#b04d36", "🗑", f"Deleted product: {product['name']}")
                self.update_products_section_title()
                self.refresh_products_ui()
                self.refresh_connected_views(include_products=True)
                self.show_notification("Product Deleted", f"{product['name']} was deleted.", "success")
            except Exception as e:
                self.show_notification("Save Error", f"Cannot delete product:\n{e}", "error", 3400)

    def open_restock_dialog(self, item_name, current_stock, inventory_id=None):
        if self.is_cashier_role():
            self.show_notification("Access Denied", "Only admins can restock inventory.", "warning", 2400)
            return
        dlg = RestockDialog(self, item_name=item_name, current_stock=current_stock)

        if dlg.exec_():
            if inventory_id is not None:
                try:
                    dlg.set_submit_state(True)
                    self.begin_busy_feedback("Restocking Item", f"Updating stock for {item_name}...")
                    qty_to_add = dlg.qty.value()
                    self.controller.restock_inventory_item(inventory_id, qty_to_add)

                    self.inventory_items = self.load_inventory_from_database()

                    self.refresh_inventory_page_if_visible()
                    self.add_recent_activity("#5d8a48", "⊕", f"Restocked: {item_name}", "Just now")
                    self.persist_order_summary_progress()
                    self.refresh_connected_views()

                    self.show_notification("Success", "Inventory updated successfully.", "success")

                except Exception as e:
                    self.show_notification("Database Error", f"Cannot update inventory:\n{e}", "error", 3400)
                finally:
                    self.end_busy_feedback()
                    dlg.set_submit_state(False)

    def show_message(self, title, text):
        self.show_notification(title, text, "info")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_notifications()
        if hasattr(self, "products_grid"):
            QTimer.singleShot(0, self.refresh_products_ui)

    def closeEvent(self, event):
        self.persist_order_summary_progress()
        super().closeEvent(event)

    def exit_to_home(self):
        self.persist_order_summary_progress()
        self.close()
        if self.login_window:
            self.login_window.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AdminDashboard()
    window.show()
    sys.exit(app.exec_())
