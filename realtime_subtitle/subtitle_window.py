from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSizeGrip, QVBoxLayout, QWidget


class SubtitleWindow(QWidget):
    def __init__(
        self,
        config: dict | None = None,
        on_close_app: Callable[[], None] | None = None,
        on_display_mode_change: Callable[[str], None] | None = None,
        on_font_size_change: Callable[[int], None] | None = None,
        on_font_color_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        config = config or {}
        window_config = config.get("subtitle_window", {})
        self._drag_position: QPoint | None = None
        self._show_border = bool(config.get("show_border", False))
        self._pinned = bool(config.get("pinned", True))
        self._background_color = str(config.get("background_color", "#000000"))
        self._font_color = str(config.get("font_color", "#ffffff"))
        self._font_size = self._clamp_font_size(config.get("font_size", 32))
        self._font_colors = ["#ffffff", "#ffe066", "#66e3ff", "#8cff8c", "#ff9bd2", "#ff6b6b"]
        self._line_mode = str(config.get("line_mode", "auto"))
        self._max_chars = int(config.get("max_chars", 120))
        self._word_wrap = bool(config.get("word_wrap", True))
        self._display_mode = str(config.get("display_mode", "translation"))
        self._on_close_app = on_close_app
        self._on_display_mode_change = on_display_mode_change
        self._on_font_size_change = on_font_size_change
        self._on_font_color_change = on_font_color_change
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

        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("subtitleToolbar")
        self.pin_button = QPushButton()
        self.translation_button = QPushButton("Trans")
        self.bilingual_button = QPushButton("Both")
        self.font_color_button = QPushButton("Color")
        self.font_down_button = QPushButton("A-")
        self.font_up_button = QPushButton("A+")
        self.close_button = QPushButton("X")
        for button in (
            self.pin_button,
            self.translation_button,
            self.bilingual_button,
            self.font_color_button,
            self.font_down_button,
            self.font_up_button,
            self.close_button,
        ):
            button.setFixedHeight(26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 2)
        toolbar_layout.setSpacing(6)
        toolbar_layout.addWidget(self.pin_button)
        toolbar_layout.addWidget(self.translation_button)
        toolbar_layout.addWidget(self.bilingual_button)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.font_color_button)
        toolbar_layout.addWidget(self.font_down_button)
        toolbar_layout.addWidget(self.font_up_button)
        toolbar_layout.addWidget(self.close_button)

        self.label = QLabel("Waiting for speech...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(self._word_wrap)
        self._apply_label_font(str(config.get("font_family", "Microsoft YaHei UI")))

        self.size_grip = QSizeGrip(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.label)

        width = int(window_config.get("width", 920))
        height = int(window_config.get("height", 150))
        x = int(window_config.get("x", 160))
        y = int(window_config.get("y", 80))
        self.setGeometry(QRect(x, y, width, height))
        self.set_opacity(float(config.get("opacity", 0.82)))
        self._apply_flags()
        self._connect_toolbar()
        self._update_toolbar()
        self.toolbar.hide()
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
        self._apply_label_font(family)

    def set_font_size(self, size: int) -> None:
        self._font_size = self._clamp_font_size(size)
        self._apply_label_font(self.label.font().family())
        if self._on_font_size_change:
            self._on_font_size_change(self._font_size)

    def font_size(self) -> int:
        return self._font_size

    def set_font_color(self, color: str) -> None:
        self._font_color = color
        self.apply_style()
        self._update_toolbar()
        if self._on_font_color_change:
            self._on_font_color_change(self._font_color)

    def font_color(self) -> str:
        return self._font_color

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
        self._update_toolbar()

    def set_display_mode(self, mode: str) -> None:
        self._display_mode = mode
        self._update_toolbar()

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

    def is_pinned(self) -> bool:
        return self._pinned

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        size = self.size_grip.sizeHint()
        self.size_grip.move(self.width() - size.width(), self.height() - size.height())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.toolbar.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.toolbar.hide()
        super().leaveEvent(event)

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
            QWidget#subtitleToolbar {{
                background-color: rgba(20, 24, 31, 225);
                border: 0;
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 35);
                color: white;
                border: 1px solid rgba(255, 255, 255, 70);
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(90, 167, 255, 120);
            }}
            QPushButton:checked {{
                background-color: rgba(90, 167, 255, 190);
            }}
            QSizeGrip {{
                background: transparent;
                width: 18px;
                height: 18px;
                border: 0;
            }}
            """
        )

    def _connect_toolbar(self) -> None:
        self.pin_button.clicked.connect(lambda: self.set_pinned(not self._pinned))
        self.translation_button.clicked.connect(lambda: self._change_display_mode("translation"))
        self.bilingual_button.clicked.connect(lambda: self._change_display_mode("bilingual"))
        self.font_color_button.clicked.connect(self._cycle_font_color)
        self.font_down_button.clicked.connect(lambda: self.set_font_size(self._font_size - 2))
        self.font_up_button.clicked.connect(lambda: self.set_font_size(self._font_size + 2))
        self.close_button.clicked.connect(lambda: self._on_close_app() if self._on_close_app else None)

    def _change_display_mode(self, mode: str) -> None:
        self._display_mode = mode
        self._update_toolbar()
        if self._on_display_mode_change:
            self._on_display_mode_change(mode)

    def _update_toolbar(self) -> None:
        self.pin_button.setText("Pinned" if self._pinned else "Pin")
        self.translation_button.setCheckable(True)
        self.bilingual_button.setCheckable(True)
        self.translation_button.setChecked(self._display_mode == "translation")
        self.bilingual_button.setChecked(self._display_mode == "bilingual")
        color = QColor(self._font_color)
        if not color.isValid():
            color = QColor("#ffffff")
        self.font_color_button.setStyleSheet(
            f"color: rgb({color.red()}, {color.green()}, {color.blue()}); font-weight: bold;"
        )

    def _cycle_font_color(self) -> None:
        current = self._font_color.lower()
        try:
            index = self._font_colors.index(current)
        except ValueError:
            index = -1
        self.set_font_color(self._font_colors[(index + 1) % len(self._font_colors)])

    def _apply_label_font(self, family: str) -> None:
        self.label.setFont(QFont(family, self._font_size, QFont.Weight.Bold))

    @staticmethod
    def _clamp_font_size(value: object) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 32
        return max(16, min(96, size))

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
