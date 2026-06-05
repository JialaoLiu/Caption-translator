from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QMouseEvent
from PyQt6.QtWidgets import QLabel, QSizeGrip, QVBoxLayout, QWidget


class SubtitleWindow(QWidget):
    def __init__(self, config: dict | None = None) -> None:
        super().__init__()
        config = config or {}
        window_config = config.get("subtitle_window", {})
        self._drag_position: QPoint | None = None
        self._show_border = bool(config.get("show_border", False))
        self._pinned = bool(config.get("pinned", True))
        self._background_color = str(config.get("background_color", "#000000"))

        self.setWindowTitle("Caption Translator Subtitle")
        self.setMinimumSize(320, 72)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.label = QLabel("Waiting for speech...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Microsoft YaHei UI", int(config.get("font_size", 32)), QFont.Weight.Bold))
        self.label.setStyleSheet("color: white; padding: 16px 22px;")

        self.size_grip = QSizeGrip(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        width = int(window_config.get("width", 920))
        height = int(window_config.get("height", 150))
        x = int(window_config.get("x", 160))
        y = int(window_config.get("y", 80))
        self.setGeometry(QRect(x, y, width, height))
        self.set_opacity(float(config.get("opacity", 0.82)))
        self._apply_flags()
        self.apply_style()

    def set_subtitle(self, text: str) -> None:
        self.label.setText(text or " ")

    def set_font_size(self, size: int) -> None:
        font = self.label.font()
        font.setPointSize(size)
        self.label.setFont(font)

    def set_opacity(self, opacity: float) -> None:
        self.setWindowOpacity(max(0.2, min(1.0, opacity)))

    def set_background_color(self, color: str) -> None:
        self._background_color = color
        self.apply_style()

    def set_border_visible(self, visible: bool) -> None:
        self._show_border = visible
        self._apply_flags()
        self.show()
        self.apply_style()

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        self._apply_flags()
        self.show()

    def state(self) -> dict:
        geometry = self.geometry()
        return {
            "x": geometry.x(),
            "y": geometry.y(),
            "width": geometry.width(),
            "height": geometry.height(),
        }

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        size = self.size_grip.sizeHint()
        self.size_grip.move(self.width() - size.width(), self.height() - size.height())

    def apply_style(self) -> None:
        color = QColor(self._background_color)
        if not color.isValid():
            color = QColor("#000000")
        border = "2px solid rgba(255, 255, 255, 170)" if self._show_border else "0"
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 190);
                border: {border};
            }}
            QSizeGrip {{
                background: transparent;
                width: 18px;
                height: 18px;
            }}
            """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_position = None
        event.accept()

    def _apply_flags(self) -> None:
        flags = Qt.WindowType.Tool
        if self._pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if not self._show_border:
            flags |= Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(flags)
