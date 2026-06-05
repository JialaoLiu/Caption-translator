from __future__ import annotations

import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import sounddevice as sd


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    channels: int
    default_samplerate: float
    is_loopback_candidate: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} ({self.index})"


@dataclass(frozen=True)
class AudioChunk:
    samples: np.ndarray
    captured_at: float


def list_input_devices() -> list[AudioDevice]:
    devices: list[AudioDevice] = []
    for index, info in enumerate(sd.query_devices()):
        channels = int(info.get("max_input_channels", 0))
        if channels <= 0:
            continue
        devices.append(
            AudioDevice(
                index=index,
                name=str(info.get("name", f"Device {index}")),
                channels=channels,
                default_samplerate=float(info.get("default_samplerate", 16000)),
            )
        )
    return devices


def list_system_output_devices() -> list[AudioDevice]:
    if sys.platform != "win32":
        return []
    devices: list[AudioDevice] = []
    for index, info in enumerate(sd.query_devices()):
        channels = int(info.get("max_output_channels", 0))
        if channels <= 0:
            continue
        devices.append(
            AudioDevice(
                index=index,
                name=str(info.get("name", f"Output {index}")),
                channels=channels,
                default_samplerate=float(info.get("default_samplerate", 16000)),
                is_loopback_candidate=True,
            )
        )
    return devices


class AudioCapture:
    def __init__(
        self,
        audio_queue: queue.Queue[AudioChunk],
        device_index: int | None,
        chunk_seconds: float,
        samplerate: int = 16000,
        audio_mode: str = "mic_plus_system",
        system_device_index: int | None = None,
    ) -> None:
        self.audio_queue = audio_queue
        self.device_index = device_index
        self.system_device_index = system_device_index
        self.audio_mode = audio_mode
        self.chunk_seconds = max(1.0, chunk_seconds)
        self.samplerate = samplerate
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._streams: list[sd.InputStream] = []
        self._lock = threading.Lock()
        self._mic_buffer: list[np.ndarray] = []
        self._system_buffer: list[np.ndarray] = []
        self._samples_per_chunk = int(self.samplerate * self.chunk_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for stream in list(self._streams):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self) -> None:
        try:
            if self.audio_mode in {"mic_only", "mic_plus_system"}:
                self._streams.append(self._open_mic_stream())
            if self.audio_mode in {"system_only", "mic_plus_system"}:
                self._streams.append(self._open_system_stream())
            for stream in self._streams:
                stream.start()
            while not self._stop_event.wait(0.05):
                self._flush_ready_chunk()
        finally:
            for stream in list(self._streams):
                try:
                    stream.close()
                except Exception:
                    pass
            self._streams.clear()

    def _open_mic_stream(self) -> sd.InputStream:
        return sd.InputStream(
            samplerate=self.samplerate,
            device=self.device_index,
            channels=1,
            dtype="float32",
            blocksize=0,
            callback=lambda indata, frames, time_info, status: self._capture_callback(
                self._mic_buffer, indata, status
            ),
        )

    def _open_system_stream(self) -> sd.InputStream:
        if sys.platform != "win32":
            raise RuntimeError("System audio capture requires Windows WASAPI loopback.")
        extra_settings = sd.WasapiSettings(loopback=True)
        device = self.system_device_index
        if device is None:
            default_devices = sd.default.device
            if isinstance(default_devices, (tuple, list)) and len(default_devices) > 1:
                device = default_devices[1]
        channels = 2
        if device is not None:
            info = sd.query_devices(device)
            channels = max(1, min(2, int(info.get("max_output_channels", 2))))
        return sd.InputStream(
            samplerate=self.samplerate,
            device=device,
            channels=channels,
            dtype="float32",
            blocksize=0,
            extra_settings=extra_settings,
            callback=lambda indata, frames, time_info, status: self._capture_callback(
                self._system_buffer, indata, status
            ),
        )

    def _capture_callback(self, target_buffer: list[np.ndarray], indata: np.ndarray, status: sd.CallbackFlags) -> None:
        if status:
            return
        mono = self._to_mono_float32(indata)
        with self._lock:
            target_buffer.append(mono)

    def _flush_ready_chunk(self) -> None:
        with self._lock:
            if self.audio_mode == "mic_only":
                if self._buffer_size(self._mic_buffer) < self._samples_per_chunk:
                    return
                chunk = self._consume(self._mic_buffer, self._samples_per_chunk)
            elif self.audio_mode == "system_only":
                if self._buffer_size(self._system_buffer) < self._samples_per_chunk:
                    return
                chunk = self._consume(self._system_buffer, self._samples_per_chunk)
            else:
                mic_ready = self._buffer_size(self._mic_buffer) >= self._samples_per_chunk
                system_ready = self._buffer_size(self._system_buffer) >= self._samples_per_chunk
                if not mic_ready and not system_ready:
                    return
                mic = self._consume_or_silence(self._mic_buffer, self._samples_per_chunk)
                system = self._consume_or_silence(self._system_buffer, self._samples_per_chunk)
                chunk = self._mix(mic, system)
        self._enqueue_latest(AudioChunk(samples=chunk, captured_at=time.perf_counter()))

    def _enqueue_latest(self, chunk: AudioChunk) -> None:
        while self.audio_queue.qsize() >= 2:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.audio_queue.put_nowait(chunk)
        except queue.Full:
            pass

    def _to_mono_float32(self, audio: np.ndarray) -> np.ndarray:
        data = audio.astype(np.float32, copy=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return self._limit(data)

    def _mix(self, mic: np.ndarray, system: np.ndarray) -> np.ndarray:
        mixed = (mic * 0.75) + (system * 0.75)
        return self._limit(mixed)

    def _limit(self, data: np.ndarray) -> np.ndarray:
        return np.clip(np.nan_to_num(data, copy=False), -0.95, 0.95).astype(np.float32, copy=False)

    def _buffer_size(self, parts: list[np.ndarray]) -> int:
        return sum(part.shape[0] for part in parts)

    def _consume_or_silence(self, parts: list[np.ndarray], samples: int) -> np.ndarray:
        if self._buffer_size(parts) < samples:
            parts.clear()
            return np.zeros(samples, dtype=np.float32)
        return self._consume(parts, samples)

    def _consume(self, parts: list[np.ndarray], samples: int) -> np.ndarray:
        data = np.concatenate(parts) if parts else np.zeros(samples, dtype=np.float32)
        chunk = data[:samples]
        remainder = data[samples:]
        parts.clear()
        if remainder.size:
            parts.append(remainder)
        return self._limit(chunk)
