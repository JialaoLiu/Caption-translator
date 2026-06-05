from __future__ import annotations

import queue
import sys
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
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
from .obs_output import SubtitleTextOutput
from .subtitle_window import SubtitleWindow
from .translator import create_translator


class UiSignals(QObject):
    subtitle_ready = pyqtSignal(str, str, str)
    status_ready = pyqtSignal(str)


class ControlWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(660, 760)

        self.config = load_config()
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=3)
        self.audio_capture: AudioCapture | None = None
        self.asr_worker: AsrWorker | None = None
        self.output = SubtitleTextOutput(subtitle_output_path(self.config))
        self.subtitle_window = SubtitleWindow(self.config)
        self.signals = UiSignals()
        self.signals.subtitle_ready.connect(self._handle_subtitle)
        self.signals.status_ready.connect(self._set_status)

        self.devices = list_input_devices()
        self._build_ui()
        self._apply_config_to_ui()
        self.subtitle_window.show()

    def _build_ui(self) -> None:
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(12)

        audio_group = QGroupBox("Audio and ASR")
        audio_form = QFormLayout(audio_group)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Default input device", None)
        for device in self.devices:
            self.audio_combo.addItem(device.label, device.index)
        audio_form.addRow("Audio input", self.audio_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        audio_form.addRow("ASR model", self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["cpu", "cuda"])
        audio_form.addRow("Device", self.device_combo)

        self.compute_combo = QComboBox()
        self.compute_combo.addItems(["int8", "float16", "float32"])
        audio_form.addRow("Compute type", self.compute_combo)

        self.source_combo = QComboBox()
        self.source_combo.addItem("auto", "auto")
        self.source_combo.addItem("Cantonese", "yue")
        self.source_combo.addItem("Mandarin", "zh")
        self.source_combo.addItem("English", "en")
        audio_form.addRow("Source language", self.source_combo)

        self.target_combo = QComboBox()
        self.target_combo.addItem("Chinese", "zh")
        self.target_combo.addItem("English", "en")
        self.target_combo.addItem("Cantonese", "yue")
        audio_form.addRow("Target language", self.target_combo)

        self.display_combo = QComboBox()
        self.display_combo.addItem("Original only", "original")
        self.display_combo.addItem("Translation only", "translation")
        self.display_combo.addItem("Bilingual", "bilingual")
        audio_form.addRow("Display mode", self.display_combo)

        self.chunk_spin = QDoubleSpinBox()
        self.chunk_spin.setRange(1.0, 8.0)
        self.chunk_spin.setSingleStep(0.5)
        self.chunk_spin.setSuffix(" s")
        audio_form.addRow("Refresh interval", self.chunk_spin)
        main_layout.addWidget(audio_group)

        translator_group = QGroupBox("Translation Backend")
        translator_form = QFormLayout(translator_group)
        self.translator_combo = QComboBox()
        self.translator_combo.addItem("Mock", "mock")
        self.translator_combo.addItem("Ollama", "ollama")
        self.translator_combo.addItem("OpenAI-compatible API", "openai_compatible")
        translator_form.addRow("Backend", self.translator_combo)

        self.ollama_url_edit = QLineEdit()
        self.ollama_model_edit = QLineEdit()
        translator_form.addRow("Ollama base URL", self.ollama_url_edit)
        translator_form.addRow("Ollama model", self.ollama_model_edit)

        self.openai_url_edit = QLineEdit()
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_edit = QLineEdit()
        translator_form.addRow("API base URL", self.openai_url_edit)
        translator_form.addRow("API key", self.openai_key_edit)
        translator_form.addRow("API model", self.openai_model_edit)
        main_layout.addWidget(translator_group)

        subtitle_group = QGroupBox("Caption Translator Subtitle Window")
        subtitle_form = QFormLayout(subtitle_group)
        self.pin_check = QCheckBox("Keep subtitle window on top")
        self.pin_check.toggled.connect(self.subtitle_window.set_pinned)
        subtitle_form.addRow("Pin", self.pin_check)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(16, 96)
        self.font_spin.valueChanged.connect(self.subtitle_window.set_font_size)
        subtitle_form.addRow("Font size", self.font_spin)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.valueChanged.connect(lambda value: self.subtitle_window.set_opacity(value / 100))
        subtitle_form.addRow("Opacity", self.opacity_slider)

        self.color_button = QPushButton("Choose background color")
        self.color_button.clicked.connect(self._choose_background_color)
        subtitle_form.addRow("Background", self.color_button)

        self.border_check = QCheckBox("Show window border")
        self.border_check.toggled.connect(self.subtitle_window.set_border_visible)
        subtitle_form.addRow("Border", self.border_check)
        main_layout.addWidget(subtitle_group)

        self.mode_label = QLabel()
        self.mode_label.setWordWrap(True)
        self.status_label = QLabel("idle")
        self.status_label.setObjectName("statusLabel")
        main_layout.addWidget(self.mode_label)
        main_layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        main_layout.addLayout(buttons)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)

        for combo in (self.device_combo, self.compute_combo, self.model_combo):
            combo.currentTextChanged.connect(self._update_mode_hint)
        self.translator_combo.currentIndexChanged.connect(self._update_translator_fields)

    def _apply_config_to_ui(self) -> None:
        self._set_combo_text(self.model_combo, self.config.get("model_size", "small"))
        self._set_combo_text(self.device_combo, self.config.get("device", "cpu"))
        self._set_combo_text(self.compute_combo, self.config.get("compute_type", "int8"))
        self._set_combo_data(self.source_combo, self.config.get("source_language", "auto"))
        self._set_combo_data(self.target_combo, self.config.get("target_language", "zh"))
        self._set_combo_data(self.display_combo, self.config.get("display_mode", "original"))
        self._set_combo_data(self.translator_combo, self.config.get("translator_backend", "mock"))
        self._set_combo_data(self.audio_combo, self.config.get("audio_device"))

        self.chunk_spin.setValue(float(self.config.get("chunk_seconds", 3.0)))
        self.font_spin.setValue(int(self.config.get("font_size", 32)))
        self.opacity_slider.setValue(int(float(self.config.get("opacity", 0.82)) * 100))
        self.border_check.setChecked(bool(self.config.get("show_border", False)))
        self.pin_check.setChecked(bool(self.config.get("pinned", True)))

        ollama = self.config.get("ollama", {})
        self.ollama_url_edit.setText(str(ollama.get("base_url", "http://127.0.0.1:11434")))
        self.ollama_model_edit.setText(str(ollama.get("model", "qwen2.5:3b")))
        openai_config = self.config.get("openai_compatible", {})
        self.openai_url_edit.setText(str(openai_config.get("base_url", "http://127.0.0.1:8000/v1")))
        self.openai_key_edit.setText(str(openai_config.get("api_key", "")))
        self.openai_model_edit.setText(str(openai_config.get("model", "qwen2.5-3b")))

        self._update_color_button()
        self._update_translator_fields()
        self._update_mode_hint()

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
                "font_size": self.font_spin.value(),
                "opacity": self.opacity_slider.value() / 100,
                "background_color": self.config.get("background_color", "#000000"),
                "show_border": self.border_check.isChecked(),
                "pinned": self.pin_check.isChecked(),
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
        self._set_status("listening")

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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.stop()
        save_config(self._collect_config())
        self.subtitle_window.close()
        event.accept()

    def _handle_subtitle(self, _original: str, _translated: str, display: str) -> None:
        self.subtitle_window.set_subtitle(display)
        self.output.write(display)

    def _set_status(self, status: str) -> None:
        self.status_label.setText(f"Status: {status}")

    def _set_controls_enabled(self, enabled: bool) -> None:
        controls = [
            self.audio_combo,
            self.model_combo,
            self.device_combo,
            self.compute_combo,
            self.source_combo,
            self.target_combo,
            self.display_combo,
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

    def _choose_background_color(self) -> None:
        current = QColor(str(self.config.get("background_color", "#000000")))
        color = QColorDialog.getColor(current, self, "Subtitle background")
        if not color.isValid():
            return
        self.config["background_color"] = color.name()
        self.subtitle_window.set_background_color(color.name())
        self._update_color_button()

    def _update_color_button(self) -> None:
        color = str(self.config.get("background_color", "#000000"))
        self.color_button.setStyleSheet(f"background-color: {color}; color: white;")

    def _update_translator_fields(self) -> None:
        backend = str(self.translator_combo.currentData())
        is_ollama = backend == "ollama"
        is_openai = backend == "openai_compatible"
        self.ollama_url_edit.setEnabled(is_ollama)
        self.ollama_model_edit.setEnabled(is_ollama)
        self.openai_url_edit.setEnabled(is_openai)
        self.openai_key_edit.setEnabled(is_openai)
        self.openai_model_edit.setEnabled(is_openai)

    def _update_mode_hint(self) -> None:
        model = self.model_combo.currentText()
        device = self.device_combo.currentText()
        compute = self.compute_combo.currentText()
        if device == "cpu" and compute == "int8":
            hint = "Low resource mode: CPU int8. Recommended for PUBG + Bilibili Live Companion."
        elif device == "cuda":
            hint = "CUDA mode: faster ASR, but it may reduce game FPS or encoder headroom."
        else:
            hint = "Custom mode. Watch CPU/GPU load while streaming."
        if model in {"medium", "large-v3"}:
            hint += " Heavy model selected."
        self.mode_label.setText(hint)

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break


def apply_optional_silicon_theme(app: QApplication) -> None:
    try:
        __import__("siui")
        app.setProperty("silicon_ui_available", True)
    except Exception:
        app.setStyleSheet(
            """
            QMainWindow, QScrollArea, QWidget {
                background: #f5f6f8;
                color: #1f2328;
            }
            QGroupBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                min-height: 30px;
                padding: 4px 12px;
            }
            #statusLabel {
                font-weight: 600;
            }
            """
        )


def run() -> int:
    app = QApplication(sys.argv)
    apply_optional_silicon_theme(app)
    window = ControlWindow()
    window.show()
    return app.exec()
