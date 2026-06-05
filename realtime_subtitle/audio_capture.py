from __future__ import annotations

import queue
import threading
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

    @property
    def label(self) -> str:
        return f"{self.name} ({self.index})"


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


class AudioCapture:
    def __init__(
        self,
        audio_queue: queue.Queue[np.ndarray],
        device_index: int | None,
        chunk_seconds: float,
        samplerate: int = 16000,
    ) -> None:
        self.audio_queue = audio_queue
        self.device_index = device_index
        self.chunk_seconds = max(1.0, chunk_seconds)
        self.samplerate = samplerate
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._buffer: list[np.ndarray] = []
        self._samples_per_chunk = int(self.samplerate * self.chunk_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        def callback(indata: np.ndarray, frames: int, _time: Any, status: sd.CallbackFlags) -> None:
            if status:
                return
            mono = indata.mean(axis=1).astype(np.float32, copy=False)
            self._buffer.append(mono.copy())
            total = sum(part.shape[0] for part in self._buffer)
            if total < self._samples_per_chunk:
                return

            chunk = np.concatenate(self._buffer)
            self._buffer.clear()
            self._enqueue_latest(chunk[: self._samples_per_chunk])

        try:
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                device=self.device_index,
                channels=1,
                dtype="float32",
                blocksize=0,
                callback=callback,
            )
            self._stream.start()
            while not self._stop_event.wait(0.2):
                pass
        finally:
            if self._stream is not None:
                self._stream.close()
                self._stream = None

    def _enqueue_latest(self, chunk: np.ndarray) -> None:
        while self.audio_queue.qsize() >= 2:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.audio_queue.put_nowait(chunk)
        except queue.Full:
            pass
