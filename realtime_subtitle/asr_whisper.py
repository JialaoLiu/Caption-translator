from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .asr_backends import FasterWhisperBackend, FunAsrBackend, OpenAICompatibleAsrBackend, Qwen3AsrBackend
from .audio_capture import AudioChunk
from .translator import BaseTranslator, TranslationRequest


@dataclass(frozen=True)
class AsrSettings:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    source_language: str = "auto"
    target_language: str = "zh_hans"
    display_mode: str = "translation"
    accuracy_mode: str = "balanced"
    beam_size: int = 5
    vad_filter: bool = True
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = False
    asr_backend: str = "faster_whisper"
    asr_model_key: str = "faster_whisper_small"
    asr_api_base_url: str = "http://127.0.0.1:8000/v1"
    asr_api_key: str = ""
    asr_api_model: str = "sensevoice"


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
        self._backend = None

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
            self.on_status(f"loading: {self.settings.asr_model_key}")
            self._backend = self._create_backend()
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

    def _create_backend(self):
        if self.settings.asr_backend == "funasr":
            return FunAsrBackend(self.settings.asr_model_key, self.settings.device)
        if self.settings.asr_backend == "qwen3_asr":
            return Qwen3AsrBackend(self.settings.asr_model_key, self.settings.device)
        if self.settings.asr_backend == "openai_asr_api":
            return OpenAICompatibleAsrBackend(
                self.settings.asr_api_base_url,
                self.settings.asr_api_key,
                self.settings.asr_api_model,
            )
        return FasterWhisperBackend(
            model_size=self.settings.model_size,
            device=self.settings.device,
            compute_type=self.settings.compute_type,
            beam_size=self.settings.beam_size,
            vad_filter=self.settings.vad_filter,
            no_speech_threshold=self.settings.no_speech_threshold,
            condition_on_previous_text=self.settings.condition_on_previous_text,
        )

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._backend is None:
            return ""
        return self._backend.transcribe(audio, self.settings.source_language)

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
