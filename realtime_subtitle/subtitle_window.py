from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QLabel, QMenu, QSizeGrip, QVBoxLayout, QWidget


class SubtitleWindow(QWidget):
    def __init__(self, config: dict | None = None, on_close_app: Callable[[], None] | None = None) -> None:
        super().__init__()
        config = config or {}
        window_config = config.get("subtitle_window", {})
        self._drag_position: QPoint | None = None
        self._show_border = bool(config.get("show_border", False))
        self._pinned = bool(config.get("pinned", True))
        self._background_color = str(config.get("background_color", "#000000"))
        self._font_color = str(config.get("font_color", "#ffffff"))
        self._line_mode = str(config.get("line_mode", "auto"))
        self._max_chars = int(config.get("max_chars", 120))
        self._word_wrap = bool(config.get("word_wrap", True))
        self._on_close_app = on_close_app
        self._menu_labels = {
            "hide": "Hide",
            "show_border": "Show Border",
            "close_app": "Close App",
        }

        self.setWindowTitle("Caption Translator Subtitle")
        self.setMinimumSize(320, 72)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.label = QLabel("Waiting for speech...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(self._word_wrap)
        self.label.setFont(
            QFont(
                str(config.get("font_family", "Microsoft YaHei UI")),
                int(config.get("font_size", 32)),
                QFont.Weight.Bold,
            )
        )

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
        display = (text or " ").strip()
        if self._max_chars > 0 and len(display) > self._max_chars:
            display = display[-self._max_chars :]
        if self._line_mode == "single":
            display = " ".join(display.splitlines())
        elif self._line_mode == "double":
            lines = [line for line in display.splitlines() if line.strip()]
            display = "\n".join(lines[:2]) if lines else display
        self.label.setText(display or " ")

    def set_font_family(self, family: str) -> None:
        font = self.label.font()
        font.setFamily(family)
        self.label.setFont(font)

    def set_font_size(self, size: int) -> None:
        font = self.label.font()
        font.setPointSize(size)
        self.label.setFont(font)

    def set_font_color(self, color: str) -> None:
        self._font_color = color
        self.apply_style()

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

    def set_line_mode(self, mode: str) -> None:
        self._line_mode = mode

    def set_max_chars(self, max_chars: int) -> None:
        self._max_chars = max_chars

    def set_word_wrap(self, enabled: bool) -> None:
        self._word_wrap = enabled
        self.label.setWordWrap(enabled)

    def set_menu_labels(self, hide: str, show_border: str, close_app: str) -> None:
        self._menu_labels = {
            "hide": hide,
            "show_border": show_border,
            "close_app": close_app,
        }

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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def apply_style(self) -> None:
        bg = QColor(self._background_color)
        if not bg.isValid():
            bg = QColor("#000000")
        fg = QColor(self._font_color)
        if not fg.isValid():
            fg = QColor("#ffffff")
        border = "2px solid rgba(255, 255, 255, 170)" if self._show_border else "0"
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 190);
                border: {border};
            }}
            QLabel {{
                color: rgba({fg.red()}, {fg.green()}, {fg.blue()}, 255);
                padding: 16px 22px;
                background: transparent;
                border: 0;
            }}
            QSizeGrip {{
                background: transparent;
                width: 18px;
                height: 18px;
                border: 0;
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

    def _show_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        hide_action = menu.addAction(self._menu_labels["hide"])
        border_action = menu.addAction(self._menu_labels["show_border"])
        border_action.setCheckable(True)
        border_action.setChecked(self._show_border)
        close_action = menu.addAction(self._menu_labels["close_app"])
        action = menu.exec(self.mapToGlobal(point))
        if action == hide_action:
            self.hide()
        elif action == border_action:
            self.set_border_visible(not self._show_border)
        elif action == close_action and self._on_close_app:
            self._on_close_app()

    def _apply_flags(self) -> None:
        flags = Qt.WindowType.Tool
        if self._pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if not self._show_border:
            flags |= Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(flags)
