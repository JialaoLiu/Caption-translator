from __future__ import annotations

import queue
import sys
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .app_config import APP_NAME, load_config, save_config, subtitle_output_path
from .asr_whisper import AsrSettings, AsrWorker
from .audio_capture import AudioCapture, list_input_devices, list_system_output_devices
from .i18n import tr
from .modern_ui import apply_modern_theme
from .obs_output import SubtitleTextOutput
from .subtitle_window import SubtitleWindow
from .translator import check_ollama_model, create_translator


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class UiSignals(QObject):
    subtitle_ready = pyqtSignal(str, str, str)
    status_ready = pyqtSignal(str)


class ControlWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.lang = str(self.config.get("app_language", "zh_CN"))
        self.setWindowTitle(APP_NAME)
        self.resize(760, 760)
        self._is_exiting = False

        self.audio_queue = queue.Queue(maxsize=3)
        self.audio_capture: AudioCapture | None = None
        self.asr_worker: AsrWorker | None = None
        self.output = SubtitleTextOutput(subtitle_output_path(self.config))
        self.subtitle_window = SubtitleWindow(self.config, on_close_app=self.exit_app)
        self.signals = UiSignals()
        self.signals.subtitle_ready.connect(self._handle_subtitle)
        self.signals.status_ready.connect(self._set_status)

        self.mic_devices = list_input_devices()
        self.system_devices = list_system_output_devices()
        self._build_ui()
        self._apply_config_to_ui()
        self._refresh_texts()
        self._check_ollama_status()
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

        self.quick_group = QGroupBox()
        quick_form = QFormLayout(self.quick_group)
        self.app_language_combo = NoWheelComboBox()
        self.app_language_combo.addItem("English", "en")
        self.app_language_combo.addItem("简体中文", "zh_CN")
        self.app_language_combo.currentIndexChanged.connect(self._change_app_language)
        quick_form.addRow(self._label("app_language"), self.app_language_combo)

        self.audio_mode_combo = NoWheelComboBox()
        self.audio_mode_combo.addItem("Mic only / 只录麦克风", "mic_only")
        self.audio_mode_combo.addItem("System only / 只录电脑声音", "system_only")
        self.audio_mode_combo.addItem("Mic + System / 麦克风+电脑声音", "mic_plus_system")
        quick_form.addRow(self._label("audio_mode"), self.audio_mode_combo)

        self.mic_combo = NoWheelComboBox()
        self.mic_combo.addItem("", None)
        for device in self.mic_devices:
            self.mic_combo.addItem(device.label, device.index)
        quick_form.addRow(self._label("audio_input"), self.mic_combo)

        self.system_combo = NoWheelComboBox()
        self.system_combo.addItem("", None)
        for device in self.system_devices:
            self.system_combo.addItem(device.label, device.index)
        quick_form.addRow(self._label("system_audio_input"), self.system_combo)

        self.source_combo = NoWheelComboBox()
        self.source_combo.addItem("auto", "auto")
        self.source_combo.addItem("Cantonese / 粤语", "yue")
        self.source_combo.addItem("Mandarin / 普通话", "zh")
        self.source_combo.addItem("English / 英语", "en")
        quick_form.addRow(self._label("source_language"), self.source_combo)

        self.target_combo = NoWheelComboBox()
        self.target_combo.addItem("Mandarin Simplified / 简体普通话", "zh_hans")
        self.target_combo.addItem("Mandarin Traditional / 繁体中文", "zh_hant")
        self.target_combo.addItem("Cantonese / 粤语", "yue")
        self.target_combo.addItem("English / 英语", "en")
        quick_form.addRow(self._label("target_language"), self.target_combo)

        self.display_combo = NoWheelComboBox()
        self.display_combo.addItem("Translation only / 只显示译文", "translation")
        self.display_combo.addItem("Bilingual / 原文+译文", "bilingual")
        self.display_combo.addItem("Original only / 只显示原文", "original")
        quick_form.addRow(self._label("display_mode"), self.display_combo)

        self.translator_combo = NoWheelComboBox()
        self.translator_combo.addItem("Ollama / 本地真实翻译", "ollama")
        self.translator_combo.addItem("Disabled / 禁用翻译", "disabled")
        self.translator_combo.addItem("OpenAI-compatible / API 翻译", "openai_compatible")
        self.translator_combo.addItem("Mock / 测试用", "mock")
        self.translator_combo.currentIndexChanged.connect(self._update_translator_fields)
        self.translator_combo.currentIndexChanged.connect(self._check_ollama_status)
        quick_form.addRow(self._label("backend"), self.translator_combo)

        self.ollama_model_combo = NoWheelComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.addItems(["qwen2.5:3b", "qwen3:4b"])
        self.ollama_model_combo.currentTextChanged.connect(self._check_ollama_status)
        quick_form.addRow(self._label("ollama_model"), self.ollama_model_combo)
        main_layout.addWidget(self.quick_group)

        self.advanced_group = QGroupBox()
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        advanced_form = QFormLayout(self.advanced_group)
        self.model_combo = NoWheelComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        advanced_form.addRow(self._label("asr_model"), self.model_combo)
        self.device_combo = NoWheelComboBox()
        self.device_combo.addItems(["cpu", "cuda"])
        advanced_form.addRow(self._label("device"), self.device_combo)
        self.compute_combo = NoWheelComboBox()
        self.compute_combo.addItems(["int8", "float16", "float32"])
        advanced_form.addRow(self._label("compute_type"), self.compute_combo)
        self.accuracy_combo = NoWheelComboBox()
        self.accuracy_combo.addItem("Low latency / 低延迟", "low_latency")
        self.accuracy_combo.addItem("Balanced / 平衡", "balanced")
        self.accuracy_combo.addItem("Accuracy first / 准确优先", "accuracy_first")
        self.accuracy_combo.currentIndexChanged.connect(self._apply_accuracy_preset)
        advanced_form.addRow(self._label("accuracy_mode"), self.accuracy_combo)
        self.beam_spin = NoWheelSpinBox()
        self.beam_spin.setRange(1, 8)
        advanced_form.addRow(self._label("beam_size"), self.beam_spin)
        self.vad_check = QCheckBox()
        advanced_form.addRow(self._label("vad_filter"), self.vad_check)
        self.no_speech_spin = NoWheelDoubleSpinBox()
        self.no_speech_spin.setRange(0.0, 1.0)
        self.no_speech_spin.setSingleStep(0.05)
        advanced_form.addRow(self._label("no_speech_threshold"), self.no_speech_spin)
        self.condition_check = QCheckBox()
        advanced_form.addRow(self._label("condition_previous"), self.condition_check)
        self.chunk_spin = NoWheelDoubleSpinBox()
        self.chunk_spin.setRange(1.0, 8.0)
        self.chunk_spin.setSingleStep(0.5)
        self.chunk_spin.setSuffix(" s")
        advanced_form.addRow(self._label("refresh_interval"), self.chunk_spin)
        self.ollama_url_edit = QLineEdit()
        advanced_form.addRow(self._label("ollama_url"), self.ollama_url_edit)
        self.openai_url_edit = QLineEdit()
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_edit = QLineEdit()
        advanced_form.addRow(self._label("api_url"), self.openai_url_edit)
        advanced_form.addRow(self._label("api_key"), self.openai_key_edit)
        advanced_form.addRow(self._label("api_model"), self.openai_model_edit)
        main_layout.addWidget(self.advanced_group)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        main_layout.addWidget(self.hint_label)
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

    def _label(self, key: str) -> QLabel:
        label = QLabel()
        label.setProperty("i18n_key", key)
        return label

    def _apply_config_to_ui(self) -> None:
        self._set_combo_data(self.app_language_combo, self.config.get("app_language", "zh_CN"))
        self._set_combo_data(self.audio_mode_combo, self.config.get("audio_mode", "mic_plus_system"))
        self._set_combo_data(self.mic_combo, self.config.get("audio_device"))
        self._set_combo_data(self.system_combo, self.config.get("system_audio_device"))
        self._set_combo_data(self.source_combo, self.config.get("source_language", "auto"))
        self._set_combo_data(self.target_combo, self.config.get("target_language", "zh_hans"))
        self._set_combo_data(self.display_combo, self.config.get("display_mode", "translation"))
        self._set_combo_data(self.translator_combo, self.config.get("translator_backend", "ollama"))
        self._set_combo_text(self.model_combo, self.config.get("model_size", "small"))
        self._set_combo_text(self.device_combo, self.config.get("device", "cpu"))
        self._set_combo_text(self.compute_combo, self.config.get("compute_type", "int8"))
        self._set_combo_data(self.accuracy_combo, self.config.get("accuracy_mode", "balanced"))
        self.beam_spin.setValue(int(self.config.get("beam_size", 5)))
        self.vad_check.setChecked(bool(self.config.get("vad_filter", True)))
        self.no_speech_spin.setValue(float(self.config.get("no_speech_threshold", 0.6)))
        self.condition_check.setChecked(bool(self.config.get("condition_on_previous_text", False)))
        self.chunk_spin.setValue(float(self.config.get("chunk_seconds", 3.0)))
        ollama = self.config.get("ollama", {})
        self.ollama_url_edit.setText(str(ollama.get("base_url", "http://127.0.0.1:11434")))
        self.ollama_model_combo.setCurrentText(str(ollama.get("model", "qwen2.5:3b")))
        openai_config = self.config.get("openai_compatible", {})
        self.openai_url_edit.setText(str(openai_config.get("base_url", "http://127.0.0.1:8000/v1")))
        self.openai_key_edit.setText(str(openai_config.get("api_key", "")))
        self.openai_model_edit.setText(str(openai_config.get("model", "qwen2.5-3b")))
        self._update_translator_fields()
        self._set_status("idle")

    def _set_combo_text(self, combo: QComboBox, text: str) -> None:
        index = combo.findText(str(text))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_combo_data(self, combo: QComboBox, data: object) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _collect_config(self) -> dict[str, Any]:
        self.config.update(
            {
                "app_language": self.app_language_combo.currentData(),
                "audio_mode": self.audio_mode_combo.currentData(),
                "audio_device": self.mic_combo.currentData(),
                "system_audio_device": self.system_combo.currentData(),
                "source_language": self.source_combo.currentData(),
                "target_language": self.target_combo.currentData(),
                "display_mode": self.display_combo.currentData(),
                "translator_backend": self.translator_combo.currentData(),
                "model_size": self.model_combo.currentText(),
                "device": self.device_combo.currentText(),
                "compute_type": self.compute_combo.currentText(),
                "accuracy_mode": self.accuracy_combo.currentData(),
                "beam_size": self.beam_spin.value(),
                "vad_filter": self.vad_check.isChecked(),
                "no_speech_threshold": self.no_speech_spin.value(),
                "condition_on_previous_text": self.condition_check.isChecked(),
                "chunk_seconds": self.chunk_spin.value(),
                "ollama": {
                    "base_url": self.ollama_url_edit.text().strip(),
                    "model": self.ollama_model_combo.currentText().strip() or "qwen2.5:3b",
                },
                "openai_compatible": {
                    "base_url": self.openai_url_edit.text().strip(),
                    "api_key": self.openai_key_edit.text().strip(),
                    "model": self.openai_model_edit.text().strip(),
                },
                "subtitle_window": self.subtitle_window.state(),
            }
        )
        return self.config

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

    def start(self) -> None:
        config = self._collect_config()
        save_config(config)
        self._drain_audio_queue()
        self.output = SubtitleTextOutput(subtitle_output_path(config))
        self.output.write("")
        self.audio_capture = AudioCapture(
            audio_queue=self.audio_queue,
            device_index=self.mic_combo.currentData(),
            system_device_index=self.system_combo.currentData(),
            audio_mode=str(self.audio_mode_combo.currentData()),
            chunk_seconds=self.chunk_spin.value(),
        )
        translator = create_translator(config)
        if getattr(translator, "disabled", False):
            self._set_status(str(getattr(translator, "reason", "translator_disabled")))
        self.asr_worker = AsrWorker(
            audio_queue=self.audio_queue,
            settings=self._settings(),
            translator=translator,
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

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.audio_mode_combo,
            self.mic_combo,
            self.system_combo,
            self.source_combo,
            self.target_combo,
            self.display_combo,
            self.translator_combo,
            self.ollama_model_combo,
            self.model_combo,
            self.device_combo,
            self.compute_combo,
            self.accuracy_combo,
            self.beam_spin,
            self.vad_check,
            self.no_speech_spin,
            self.condition_check,
            self.chunk_spin,
            self.ollama_url_edit,
            self.openai_url_edit,
            self.openai_key_edit,
            self.openai_model_edit,
        ):
            control.setEnabled(enabled)

    def _update_translator_fields(self) -> None:
        backend = str(self.translator_combo.currentData())
        running = self.asr_worker is not None
        self.ollama_model_combo.setEnabled(backend == "ollama" and not running)
        self.ollama_url_edit.setEnabled(backend == "ollama" and not running)
        self.openai_url_edit.setEnabled(backend == "openai_compatible" and not running)
        self.openai_key_edit.setEnabled(backend == "openai_compatible" and not running)
        self.openai_model_edit.setEnabled(backend == "openai_compatible" and not running)

    def _check_ollama_status(self) -> None:
        if str(self.translator_combo.currentData()) != "ollama":
            return
        base_url = self.ollama_url_edit.text().strip() if hasattr(self, "ollama_url_edit") else "http://127.0.0.1:11434"
        model = self.ollama_model_combo.currentText().strip() if hasattr(self, "ollama_model_combo") else "qwen2.5:3b"
        ok, reason = check_ollama_model(base_url or "http://127.0.0.1:11434", model or "qwen2.5:3b")
        if ok:
            self.hint_label.setText(tr(self.lang, "ollama_ready"))
        elif reason == "ollama_model_missing":
            self.hint_label.setText(f"{tr(self.lang, 'ollama_model_missing')} ollama pull {model or 'qwen2.5:3b'}")
        else:
            self.hint_label.setText(tr(self.lang, "ollama_unavailable"))

    def _set_status(self, status: str) -> None:
        status_map = {
            "idle": tr(self.lang, "idle"),
            "listening": tr(self.lang, "listening"),
            "transcribing": tr(self.lang, "transcribing"),
            "translating": tr(self.lang, "translating"),
            "ollama_unavailable": tr(self.lang, "ollama_unavailable"),
            "ollama_model_missing": tr(self.lang, "ollama_model_missing"),
            "translator_disabled": tr(self.lang, "translator_disabled"),
        }
        if status.startswith("error:"):
            text = f"{tr(self.lang, 'status')}: {tr(self.lang, 'error')} - {status[6:].strip()}"
        elif status.startswith("loading:"):
            text = f"{tr(self.lang, 'status')}: {status}"
        else:
            text = f"{tr(self.lang, 'status')}: {status_map.get(status, status)}"
        self.status_label.setText(text)

    def _apply_accuracy_preset(self) -> None:
        mode = str(self.accuracy_combo.currentData())
        if mode == "low_latency":
            self.beam_spin.setValue(2)
        elif mode == "accuracy_first":
            self.beam_spin.setValue(8)
        else:
            self.beam_spin.setValue(5)

    def _change_app_language(self) -> None:
        self.lang = str(self.app_language_combo.currentData())
        self.config["app_language"] = self.lang
        self._refresh_texts()
        self._set_status("idle")
        self._check_ollama_status()

    def _refresh_texts(self) -> None:
        self.file_menu.setTitle(tr(self.lang, "file"))
        self.exit_action.setText(tr(self.lang, "exit"))
        self.quick_group.setTitle(tr(self.lang, "quick_settings"))
        self.advanced_group.setTitle(tr(self.lang, "advanced_settings"))
        self.start_button.setText(tr(self.lang, "start"))
        self.stop_button.setText(tr(self.lang, "stop"))
        self.exit_button.setText(tr(self.lang, "exit"))
        self.mic_combo.setItemText(0, tr(self.lang, "default_input"))
        self.system_combo.setItemText(0, tr(self.lang, "default_system_output"))
        self.subtitle_window.set_menu_labels(tr(self.lang, "hide"), tr(self.lang, "show_border"), tr(self.lang, "close_app"))
        for label in self.findChildren(QLabel):
            key = label.property("i18n_key")
            if key:
                label.setText(tr(self.lang, str(key)))

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
