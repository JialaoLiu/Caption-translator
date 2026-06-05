from __future__ import annotations

import queue
import sys
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .app_config import APP_NAME, load_config, save_config, subtitle_output_path
from .asr_whisper import AsrSettings, AsrWorker
from .audio_capture import AudioCapture, list_input_devices
from .i18n import tr
from .modern_ui import apply_modern_theme
from .obs_output import SubtitleTextOutput
from .subtitle_window import SubtitleWindow
from .translator import create_translator


class UiSignals(QObject):
    subtitle_ready = pyqtSignal(str, str, str)
    status_ready = pyqtSignal(str)


class ControlWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.lang = str(self.config.get("app_language", "en"))
        self.setWindowTitle(APP_NAME)
        self.resize(760, 860)
        self._is_exiting = False

        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=3)
        self.audio_capture: AudioCapture | None = None
        self.asr_worker: AsrWorker | None = None
        self.output = SubtitleTextOutput(subtitle_output_path(self.config))
        self.subtitle_window = SubtitleWindow(self.config, on_close_app=self.exit_app)
        self.signals = UiSignals()
        self.signals.subtitle_ready.connect(self._handle_subtitle)
        self.signals.status_ready.connect(self._set_status)

        self.devices = list_input_devices()
        self._build_ui()
        self._apply_config_to_ui()
        self._refresh_texts()
        self.subtitle_window.show()

    def _build_ui(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.exit_action = QAction("", self)
        self.exit_action.triggered.connect(self.exit_app)
        self.file_menu.addAction(self.exit_action)

        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 16, 18, 18)

        self.app_group = QGroupBox()
        app_form = QFormLayout(self.app_group)
        self.app_language_combo = QComboBox()
        self.app_language_combo.addItem("English", "en")
        self.app_language_combo.addItem("简体中文", "zh_CN")
        self.app_language_combo.currentIndexChanged.connect(self._change_app_language)
        app_form.addRow(self._label("app_language"), self.app_language_combo)
        main_layout.addWidget(self.app_group)

        self.audio_group = QGroupBox()
        audio_form = QFormLayout(self.audio_group)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("", None)
        for device in self.devices:
            self.audio_combo.addItem(device.label, device.index)
        audio_form.addRow(self._label("audio_input"), self.audio_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        audio_form.addRow(self._label("asr_model"), self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda"])
        audio_form.addRow(self._label("device"), self.device_combo)

        self.compute_combo = QComboBox()
        self.compute_combo.addItems(["int8", "float16", "float32"])
        audio_form.addRow(self._label("compute_type"), self.compute_combo)

        self.source_combo = QComboBox()
        self._fill_source_languages()
        audio_form.addRow(self._label("source_language"), self.source_combo)

        self.target_combo = QComboBox()
        self._fill_target_languages()
        audio_form.addRow(self._label("target_language"), self.target_combo)

        self.display_combo = QComboBox()
        self.display_combo.addItem("Original only", "original")
        self.display_combo.addItem("Translation only", "translation")
        self.display_combo.addItem("Bilingual", "bilingual")
        audio_form.addRow(self._label("display_mode"), self.display_combo)

        self.accuracy_combo = QComboBox()
        self.accuracy_combo.addItem("Low latency", "low_latency")
        self.accuracy_combo.addItem("Balanced", "balanced")
        self.accuracy_combo.addItem("Accuracy first", "accuracy_first")
        self.accuracy_combo.currentIndexChanged.connect(self._apply_accuracy_preset)
        audio_form.addRow(self._label("accuracy_mode"), self.accuracy_combo)

        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 8)
        audio_form.addRow(self._label("beam_size"), self.beam_spin)

        self.vad_check = QCheckBox()
        audio_form.addRow(self._label("vad_filter"), self.vad_check)

        self.no_speech_spin = QDoubleSpinBox()
        self.no_speech_spin.setRange(0.0, 1.0)
        self.no_speech_spin.setSingleStep(0.05)
        audio_form.addRow(self._label("no_speech_threshold"), self.no_speech_spin)

        self.condition_check = QCheckBox()
        audio_form.addRow(self._label("condition_previous"), self.condition_check)

        self.chunk_spin = QDoubleSpinBox()
        self.chunk_spin.setRange(1.0, 8.0)
        self.chunk_spin.setSingleStep(0.5)
        self.chunk_spin.setSuffix(" s")
        audio_form.addRow(self._label("refresh_interval"), self.chunk_spin)
        main_layout.addWidget(self.audio_group)

        self.translator_group = QGroupBox()
        translator_form = QFormLayout(self.translator_group)
        self.translator_combo = QComboBox()
        self.translator_combo.addItem("Mock - testing only, no real translation", "mock")
        self.translator_combo.addItem("Ollama - local real translation", "ollama")
        self.translator_combo.addItem("OpenAI-compatible - API real translation", "openai_compatible")
        translator_form.addRow(self._label("backend"), self.translator_combo)
        self.ollama_url_edit = QLineEdit()
        self.ollama_model_edit = QLineEdit()
        translator_form.addRow(self._label("ollama_url"), self.ollama_url_edit)
        translator_form.addRow(self._label("ollama_model"), self.ollama_model_edit)
        self.openai_url_edit = QLineEdit()
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_edit = QLineEdit()
        translator_form.addRow(self._label("api_url"), self.openai_url_edit)
        translator_form.addRow(self._label("api_key"), self.openai_key_edit)
        translator_form.addRow(self._label("api_model"), self.openai_model_edit)
        main_layout.addWidget(self.translator_group)

        self.subtitle_group = QGroupBox()
        subtitle_form = QFormLayout(self.subtitle_group)
        self.pin_check = QCheckBox()
        self.pin_check.toggled.connect(self.subtitle_window.set_pinned)
        subtitle_form.addRow(self._label("keep_on_top"), self.pin_check)

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(lambda font: self.subtitle_window.set_font_family(font.family()))
        subtitle_form.addRow(self._label("font_family"), self.font_combo)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(16, 96)
        self.font_spin.valueChanged.connect(self.subtitle_window.set_font_size)
        subtitle_form.addRow(self._label("font_size"), self.font_spin)

        self.font_color_button = QPushButton()
        self.font_color_button.clicked.connect(lambda: self._choose_color("font_color"))
        subtitle_form.addRow(self._label("font_color"), self.font_color_button)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.valueChanged.connect(lambda value: self.subtitle_window.set_opacity(value / 100))
        subtitle_form.addRow(self._label("opacity"), self.opacity_slider)

        self.background_button = QPushButton()
        self.background_button.clicked.connect(lambda: self._choose_color("background_color"))
        subtitle_form.addRow(self._label("background"), self.background_button)

        self.border_check = QCheckBox()
        self.border_check.toggled.connect(self.subtitle_window.set_border_visible)
        subtitle_form.addRow(self._label("show_border"), self.border_check)

        self.line_mode_combo = QComboBox()
        self.line_mode_combo.addItem("Auto", "auto")
        self.line_mode_combo.addItem("Single line", "single")
        self.line_mode_combo.addItem("Double line", "double")
        self.line_mode_combo.currentIndexChanged.connect(lambda: self.subtitle_window.set_line_mode(str(self.line_mode_combo.currentData())))
        subtitle_form.addRow(self._label("line_mode"), self.line_mode_combo)

        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(20, 500)
        self.max_chars_spin.valueChanged.connect(self.subtitle_window.set_max_chars)
        subtitle_form.addRow(self._label("max_chars"), self.max_chars_spin)

        self.word_wrap_check = QCheckBox()
        self.word_wrap_check.toggled.connect(self.subtitle_window.set_word_wrap)
        subtitle_form.addRow(self._label("word_wrap"), self.word_wrap_check)
        main_layout.addWidget(self.subtitle_group)

        self.mode_label = QLabel()
        self.mode_label.setObjectName("hintLabel")
        self.mode_label.setWordWrap(True)
        self.cantonese_hint_label = QLabel()
        self.cantonese_hint_label.setObjectName("hintLabel")
        self.cantonese_hint_label.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        main_layout.addWidget(self.mode_label)
        main_layout.addWidget(self.cantonese_hint_label)
        main_layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.start_button = QPushButton()
        self.stop_button = QPushButton()
        self.exit_button = QPushButton()
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.exit_button.clicked.connect(self.exit_app)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.exit_button)
        main_layout.addLayout(buttons)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)

        for combo in (self.device_combo, self.compute_combo, self.model_combo, self.source_combo, self.display_combo):
            combo.currentIndexChanged.connect(self._update_mode_hint)
        self.translator_combo.currentIndexChanged.connect(self._update_translator_fields)
        self.translator_combo.currentIndexChanged.connect(self._update_mode_hint)

    def _label(self, key: str) -> QLabel:
        label = QLabel()
        label.setProperty("i18n_key", key)
        return label

    def _fill_source_languages(self) -> None:
        self.source_combo.clear()
        self.source_combo.addItem("auto", "auto")
        self.source_combo.addItem("Cantonese / 粤语", "yue")
        self.source_combo.addItem("Mandarin / 普通话", "zh")
        self.source_combo.addItem("English / English", "en")

    def _fill_target_languages(self) -> None:
        self.target_combo.clear()
        self.target_combo.addItem("Mandarin Simplified / 简体普通话", "zh_hans")
        self.target_combo.addItem("Mandarin Traditional / 繁体中文", "zh_hant")
        self.target_combo.addItem("Cantonese / 粤语", "yue")
        self.target_combo.addItem("English / English", "en")

    def _apply_config_to_ui(self) -> None:
        self._set_combo_data(self.app_language_combo, self.config.get("app_language", "en"))
        self._set_combo_text(self.model_combo, self.config.get("model_size", "small"))
        self._set_combo_text(self.device_combo, self.config.get("device", "cpu"))
        self._set_combo_text(self.compute_combo, self.config.get("compute_type", "int8"))
        self._set_combo_data(self.source_combo, self.config.get("source_language", "auto"))
        self._set_combo_data(self.target_combo, self.config.get("target_language", "zh_hans"))
        self._set_combo_data(self.display_combo, self.config.get("display_mode", "original"))
        self._set_combo_data(self.accuracy_combo, self.config.get("accuracy_mode", "balanced"))
        self._set_combo_data(self.translator_combo, self.config.get("translator_backend", "mock"))
        self._set_combo_data(self.audio_combo, self.config.get("audio_device"))
        self._set_combo_data(self.line_mode_combo, self.config.get("line_mode", "auto"))

        self.beam_spin.setValue(int(self.config.get("beam_size", 5)))
        self.vad_check.setChecked(bool(self.config.get("vad_filter", True)))
        self.no_speech_spin.setValue(float(self.config.get("no_speech_threshold", 0.6)))
        self.condition_check.setChecked(bool(self.config.get("condition_on_previous_text", False)))
        self.chunk_spin.setValue(float(self.config.get("chunk_seconds", 3.0)))
        self.font_combo.setCurrentFont(self.subtitle_window.label.font())
        self.font_spin.setValue(int(self.config.get("font_size", 32)))
        self.opacity_slider.setValue(int(float(self.config.get("opacity", 0.82)) * 100))
        self.border_check.setChecked(bool(self.config.get("show_border", False)))
        self.pin_check.setChecked(bool(self.config.get("pinned", True)))
        self.max_chars_spin.setValue(int(self.config.get("max_chars", 120)))
        self.word_wrap_check.setChecked(bool(self.config.get("word_wrap", True)))

        ollama = self.config.get("ollama", {})
        self.ollama_url_edit.setText(str(ollama.get("base_url", "http://127.0.0.1:11434")))
        self.ollama_model_edit.setText(str(ollama.get("model", "qwen2.5:3b")))
        openai_config = self.config.get("openai_compatible", {})
        self.openai_url_edit.setText(str(openai_config.get("base_url", "http://127.0.0.1:8000/v1")))
        self.openai_key_edit.setText(str(openai_config.get("api_key", "")))
        self.openai_model_edit.setText(str(openai_config.get("model", "qwen2.5-3b")))

        self._update_color_buttons()
        self._update_translator_fields()
        self._update_mode_hint()
        self._set_status("idle")

    def _set_combo_text(self, combo: QComboBox, text: str) -> None:
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_combo_data(self, combo: QComboBox, data: object) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _settings(self) -> AsrSettings:
        return AsrSettings(
            model_size=self.model_combo.currentText(),
            device=self.device_combo.currentText(),
            compute_type=self.compute_combo.currentText(),
            source_language=str(self.source_combo.currentData()),
            target_language=str(self.target_combo.currentData()),
            display_mode=str(self.display_combo.currentData()),
            accuracy_mode=str(self.accuracy_combo.currentData()),
            beam_size=self.beam_spin.value(),
            vad_filter=self.vad_check.isChecked(),
            no_speech_threshold=self.no_speech_spin.value(),
            condition_on_previous_text=self.condition_check.isChecked(),
        )

    def _collect_config(self) -> dict[str, Any]:
        self.config.update(
            {
                "audio_device": self.audio_combo.currentData(),
                "model_size": self.model_combo.currentText(),
                "device": self.device_combo.currentText(),
                "compute_type": self.compute_combo.currentText(),
                "source_language": self.source_combo.currentData(),
                "target_language": self.target_combo.currentData(),
                "display_mode": self.display_combo.currentData(),
                "app_language": self.app_language_combo.currentData(),
                "accuracy_mode": self.accuracy_combo.currentData(),
                "beam_size": self.beam_spin.value(),
                "vad_filter": self.vad_check.isChecked(),
                "no_speech_threshold": self.no_speech_spin.value(),
                "condition_on_previous_text": self.condition_check.isChecked(),
                "translator_backend": self.translator_combo.currentData(),
                "ollama": {
                    "base_url": self.ollama_url_edit.text().strip(),
                    "model": self.ollama_model_edit.text().strip(),
                },
                "openai_compatible": {
                    "base_url": self.openai_url_edit.text().strip(),
                    "api_key": self.openai_key_edit.text().strip(),
                    "model": self.openai_model_edit.text().strip(),
                },
                "chunk_seconds": self.chunk_spin.value(),
                "font_family": self.font_combo.currentFont().family(),
                "font_size": self.font_spin.value(),
                "font_color": self.config.get("font_color", "#ffffff"),
                "opacity": self.opacity_slider.value() / 100,
                "background_color": self.config.get("background_color", "#000000"),
                "show_border": self.border_check.isChecked(),
                "pinned": self.pin_check.isChecked(),
                "line_mode": self.line_mode_combo.currentData(),
                "max_chars": self.max_chars_spin.value(),
                "word_wrap": self.word_wrap_check.isChecked(),
                "subtitle_window": self.subtitle_window.state(),
            }
        )
        return self.config

    def start(self) -> None:
        config = self._collect_config()
        save_config(config)
        self.output = SubtitleTextOutput(subtitle_output_path(config))
        self._drain_audio_queue()
        self.output.write("")
        if self.display_combo.currentData() != "original" and self.translator_combo.currentData() == "mock":
            self._set_status("mock_warning")

        self.audio_capture = AudioCapture(
            audio_queue=self.audio_queue,
            device_index=self.audio_combo.currentData(),
            chunk_seconds=self.chunk_spin.value(),
        )
        self.asr_worker = AsrWorker(
            audio_queue=self.audio_queue,
            settings=self._settings(),
            translator=create_translator(config),
            on_text=lambda original, translated, display: self.signals.subtitle_ready.emit(original, translated, display),
            on_status=lambda status: self.signals.status_ready.emit(status),
        )
        self.audio_capture.start()
        self.asr_worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_controls_enabled(False)

    def stop(self) -> None:
        if self.audio_capture:
            self.audio_capture.stop()
            self.audio_capture = None
        if self.asr_worker:
            self.asr_worker.stop()
            self.asr_worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._set_controls_enabled(True)
        self._update_translator_fields()
        self._set_status("idle")

    def exit_app(self) -> None:
        if self._is_exiting:
            return
        self._is_exiting = True
        self.stop()
        save_config(self._collect_config())
        self.subtitle_window.close()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.exit_app()
        event.accept()

    def _handle_subtitle(self, _original: str, _translated: str, display: str) -> None:
        self.subtitle_window.set_subtitle(display)
        self.output.write(display)

    def _set_status(self, status: str) -> None:
        if status == "mock_warning":
            text = tr(self.lang, "mock_warning")
        elif status.startswith("error:"):
            text = f"{tr(self.lang, 'status')}: {tr(self.lang, 'error')} - {status[6:].strip()}"
        elif status.startswith("loading:"):
            text = f"{tr(self.lang, 'status')}: {status}"
        else:
            text = f"{tr(self.lang, 'status')}: {tr(self.lang, status)}"
        self.status_label.setText(text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        controls = [
            self.audio_combo,
            self.model_combo,
            self.device_combo,
            self.compute_combo,
            self.source_combo,
            self.target_combo,
            self.display_combo,
            self.accuracy_combo,
            self.beam_spin,
            self.vad_check,
            self.no_speech_spin,
            self.condition_check,
            self.chunk_spin,
            self.translator_combo,
            self.ollama_url_edit,
            self.ollama_model_edit,
            self.openai_url_edit,
            self.openai_key_edit,
            self.openai_model_edit,
        ]
        for control in controls:
            control.setEnabled(enabled)

    def _choose_color(self, key: str) -> None:
        current = QColor(str(self.config.get(key, "#000000")))
        color = QColorDialog.getColor(current, self, tr(self.lang, "choose_color"))
        if not color.isValid():
            return
        self.config[key] = color.name()
        if key == "background_color":
            self.subtitle_window.set_background_color(color.name())
        else:
            self.subtitle_window.set_font_color(color.name())
        self._update_color_buttons()

    def _update_color_buttons(self) -> None:
        bg = str(self.config.get("background_color", "#000000"))
        fg = str(self.config.get("font_color", "#ffffff"))
        self.background_button.setText(bg)
        self.background_button.setStyleSheet(f"background-color: {bg}; color: white;")
        self.font_color_button.setText(fg)
        self.font_color_button.setStyleSheet(f"background-color: {fg}; color: black;")

    def _update_translator_fields(self) -> None:
        backend = str(self.translator_combo.currentData())
        is_ollama = backend == "ollama"
        is_openai = backend == "openai_compatible"
        running = self.asr_worker is not None
        self.ollama_url_edit.setEnabled(is_ollama and not running)
        self.ollama_model_edit.setEnabled(is_ollama and not running)
        self.openai_url_edit.setEnabled(is_openai and not running)
        self.openai_key_edit.setEnabled(is_openai and not running)
        self.openai_model_edit.setEnabled(is_openai and not running)

    def _apply_accuracy_preset(self) -> None:
        mode = str(self.accuracy_combo.currentData())
        if mode == "low_latency":
            if self.model_combo.currentText() not in {"tiny", "base", "small"}:
                self.model_combo.setCurrentText("small")
            self.beam_spin.setValue(2)
        elif mode == "accuracy_first":
            if self.model_combo.currentText() in {"tiny", "base"}:
                self.model_combo.setCurrentText("medium")
            self.beam_spin.setValue(8)
        else:
            if self.model_combo.currentText() == "tiny":
                self.model_combo.setCurrentText("small")
            self.beam_spin.setValue(5)
        self._update_mode_hint()

    def _change_app_language(self) -> None:
        self.lang = str(self.app_language_combo.currentData())
        self.config["app_language"] = self.lang
        self._refresh_texts()
        self._set_status("idle")

    def _refresh_texts(self) -> None:
        self.file_menu.setTitle(tr(self.lang, "file"))
        self.exit_action.setText(tr(self.lang, "exit"))
        self.app_group.setTitle(tr(self.lang, "app_language"))
        self.audio_group.setTitle(tr(self.lang, "audio_asr"))
        self.translator_group.setTitle(tr(self.lang, "translation_backend"))
        self.subtitle_group.setTitle(tr(self.lang, "subtitle_window"))
        self.start_button.setText(tr(self.lang, "start"))
        self.stop_button.setText(tr(self.lang, "stop"))
        self.exit_button.setText(tr(self.lang, "exit"))
        self.cantonese_hint_label.setText(tr(self.lang, "cantonese_hint"))
        self.subtitle_window.set_menu_labels(
            tr(self.lang, "hide"),
            tr(self.lang, "show_border"),
            tr(self.lang, "close_app"),
        )
        self.audio_combo.setItemText(0, tr(self.lang, "default_input"))
        for label in self.findChildren(QLabel):
            key = label.property("i18n_key")
            if key:
                label.setText(tr(self.lang, str(key)))
        self._update_mode_hint()

    def _update_mode_hint(self) -> None:
        model = self.model_combo.currentText()
        device = self.device_combo.currentText()
        compute = self.compute_combo.currentText()
        if device == "cpu" and compute == "int8":
            hint = tr(self.lang, "mode_low")
        elif device == "cuda":
            hint = tr(self.lang, "mode_cuda")
        else:
            hint = tr(self.lang, "mode_custom")
        if model in {"medium", "large-v3"}:
            hint += tr(self.lang, "heavy_model")
        if self.display_combo.currentData() != "original" and self.translator_combo.currentData() == "mock":
            hint += f" {tr(self.lang, 'mock_warning')}"
        self.mode_label.setText(hint)

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break


def run() -> int:
    app = QApplication(sys.argv)
    apply_modern_theme(app)
    window = ControlWindow()
    window.show()
    return app.exec()
