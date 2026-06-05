from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np
from faster_whisper import WhisperModel

from .audio_capture import AudioChunk
from .translator import BaseTranslator, TranslationRequest


LANGUAGE_MAP = {
    "auto": None,
    "yue": "zh",
    "zh": "zh",
    "en": "en",
}


@dataclass(frozen=True)
class AsrSettings:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    source_language: str = "auto"
    target_language: str = "zh_hans"
    display_mode: str = "original"
    accuracy_mode: str = "balanced"
    beam_size: int = 5
    vad_filter: bool = True
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False


class AsrWorker:
    def __init__(
        self,
        audio_queue: queue.Queue[AudioChunk],
        settings: AsrSettings,
        translator: BaseTranslator,
        on_text: Callable[[str, str, str], None],
        on_status: Callable[[str], None],
    ) -> None:
        self.audio_queue = audio_queue
        self.settings = settings
        self.translator = translator
        self.on_text = on_text
        self.on_status = on_status
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._model: WhisperModel | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="asr-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        try:
            self.on_status(f"loading: {self.settings.model_size} on {self.settings.device}/{self.settings.compute_type}")
            self._model = WhisperModel(
                self.settings.model_size,
                device=self.settings.device,
                compute_type=self.settings.compute_type,
            )
            self.on_status("listening")
            while not self._stop_event.is_set():
                try:
                    audio = self.audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                self.on_status("transcribing")
                original = self._transcribe(audio.samples)
                if not original:
                    self.on_status("listening")
                    continue
                if self.settings.display_mode != "original":
                    self.on_status("translating")
                translated = self._translate(original)
                latency_ms = int((time.perf_counter() - audio.captured_at) * 1000)
                display = self._format_display(original, translated, latency_ms)
                self.on_text(original, translated, display)
                self.on_status("listening")
        except Exception as exc:
            self.on_status(f"error: {exc}")

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            return ""
        language = LANGUAGE_MAP.get(self.settings.source_language)
        segments, _info = self._model.transcribe(
            audio,
            language=language,
            beam_size=self.settings.beam_size,
            vad_filter=self.settings.vad_filter,
            no_speech_threshold=self.settings.no_speech_threshold,
            condition_on_previous_text=self.settings.condition_on_previous_text,
            without_timestamps=True,
        )
        text = "".join(segment.text for segment in segments).strip()
        return text

    def _translate(self, text: str) -> str:
        if self.settings.display_mode == "original" or getattr(self.translator, "disabled", False):
            return ""
        request = TranslationRequest(
            text=text,
            source_language=self.settings.source_language,
            target_language=self.settings.target_language,
        )
        return self.translator.translate(request)

    def _format_display(self, original: str, translated: str, latency_ms: int) -> str:
        prefix = f"[{latency_ms}ms] "
        if getattr(self.translator, "disabled", False):
            return f"{prefix}{original}"
        if self.settings.display_mode == "translation":
            return f"{prefix}{translated or original}"
        if self.settings.display_mode == "bilingual":
            return f"{original}\n{prefix}{translated}" if translated else f"{prefix}{original}"
        return f"{prefix}{original}"
