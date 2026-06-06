from __future__ import annotations

import queue
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

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
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.audio_queue = audio_queue
        self.device_index = device_index
        self.system_device_index = system_device_index
        self.audio_mode = audio_mode
        self.on_status = on_status
        self.chunk_seconds = max(1.0, chunk_seconds)
        self.samplerate = samplerate
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._system_thread: threading.Thread | None = None
        self._streams: list[sd.InputStream] = []
        self._lock = threading.Lock()
        self._mic_buffer: list[np.ndarray] = []
        self._system_buffer: list[np.ndarray] = []
        self._samples_per_chunk = int(self.samplerate * self.chunk_seconds)
        self._last_status_report = 0.0
        self._last_level_report = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="audio-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._system_thread and self._system_thread.is_alive():
            self._system_thread.join(timeout=3)
        for stream in list(self._streams):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._streams.clear()

    def _run(self) -> None:
        try:
            system_started = False
            if self.audio_mode in {"mic_only", "mic_plus_system"}:
                self._try_open_stream("mic", self._open_mic_stream)
            if self.audio_mode in {"system_only", "mic_plus_system"}:
                system_started = self._try_start_system_loopback()
            if not self._streams and not system_started:
                raise RuntimeError("No audio input stream could be opened.")
            for stream in self._streams:
                stream.start()
            self._report("audio: capture started")
            while not self._stop_event.wait(0.05):
                self._flush_ready_chunk()
        except Exception as exc:
            self._report(f"audio_error: {exc}")
        finally:
            for stream in list(self._streams):
                try:
                    stream.close()
                except Exception:
                    pass
            self._streams.clear()

    def _try_open_stream(self, name: str, opener: Callable[[], sd.InputStream]) -> None:
        try:
            self._streams.append(opener())
        except Exception as exc:
            self._report(f"audio_error: {name} stream failed: {exc}")
            if self.audio_mode in {"mic_only", "system_only"}:
                raise

    def _try_start_system_loopback(self) -> bool:
        try:
            loopback = self._select_soundcard_loopback()
            self._system_thread = threading.Thread(
                target=self._system_loopback_worker,
                args=(loopback,),
                name="system-loopback",
                daemon=True,
            )
            self._system_thread.start()
            self._report(f"audio: system loopback started: {loopback.name}")
            return True
        except Exception as exc:
            self._report(f"audio_error: system stream failed: {exc}")
            if self.audio_mode == "system_only":
                raise
            return False

    def _open_mic_stream(self) -> sd.InputStream:
        samplerate = self._device_samplerate(self.device_index, input_device=True)
        return sd.InputStream(
            samplerate=samplerate,
            device=self.device_index,
            channels=1,
            dtype="float32",
            blocksize=0,
            callback=lambda indata, frames, time_info, status: self._capture_callback(
                self._mic_buffer, indata, status, samplerate
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
        samplerate = self._device_samplerate(device, input_device=False)
        return sd.InputStream(
            samplerate=samplerate,
            device=device,
            channels=channels,
            dtype="float32",
            blocksize=0,
            extra_settings=extra_settings,
            callback=lambda indata, frames, time_info, status: self._capture_callback(
                self._system_buffer, indata, status, samplerate
            ),
        )

    def _capture_callback(
        self,
        target_buffer: list[np.ndarray],
        indata: np.ndarray,
        status: sd.CallbackFlags,
        input_samplerate: int,
    ) -> None:
        if status:
            self._report_throttled(f"audio_warning: {status}")
        mono = self._to_mono_float32(indata)
        mono = self._resample(mono, input_samplerate, self.samplerate)
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
        self._report_level(chunk)
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

    def _resample(self, data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if source_rate == target_rate or data.size == 0:
            return data.astype(np.float32, copy=False)
        target_size = max(1, int(data.shape[0] * target_rate / source_rate))
        old_positions = np.linspace(0.0, 1.0, num=data.shape[0], endpoint=False)
        new_positions = np.linspace(0.0, 1.0, num=target_size, endpoint=False)
        return np.interp(new_positions, old_positions, data).astype(np.float32, copy=False)

    def _device_samplerate(self, device_index: int | None, input_device: bool) -> int:
        try:
            if device_index is None:
                default_devices = sd.default.device
                if isinstance(default_devices, (tuple, list)):
                    device_index = default_devices[0 if input_device else 1]
            info = sd.query_devices(device_index) if device_index is not None else sd.query_devices(kind="input" if input_device else "output")
            return int(float(info.get("default_samplerate", self.samplerate)))
        except Exception:
            return self.samplerate

    def _report(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _report_throttled(self, message: str, interval: float = 2.0) -> None:
        now = time.perf_counter()
        if now - self._last_status_report >= interval:
            self._last_status_report = now
            self._report(message)

    def _report_level(self, chunk: np.ndarray) -> None:
        now = time.perf_counter()
        if now - self._last_level_report < 3.0 or chunk.size == 0:
            return
        self._last_level_report = now
        rms = float(np.sqrt(np.mean(chunk * chunk)))
        peak = float(np.max(np.abs(chunk)))
        if peak < 0.003:
            self._report(f"audio_warning: input level is very low, rms={rms:.4f}, peak={peak:.4f}")
        else:
            self._report(f"audio: input level rms={rms:.4f}, peak={peak:.4f}")

    def _select_soundcard_loopback(self) -> Any:
        if sys.platform != "win32":
            raise RuntimeError("System audio capture requires Windows WASAPI loopback.")
        try:
            import soundcard as sc
        except Exception as exc:
            raise RuntimeError("Missing dependency: pip install soundcard") from exc
        loopbacks = list(sc.all_microphones(include_loopback=True))
        loopbacks = [device for device in loopbacks if getattr(device, "isloopback", False)]
        if not loopbacks:
            raise RuntimeError("No WASAPI loopback device found.")
        target_name = ""
        if self.system_device_index is not None:
            try:
                target_name = str(sd.query_devices(self.system_device_index).get("name", ""))
            except Exception:
                target_name = ""
        if target_name:
            normalized_target = _normalize_device_name(target_name)
            for device in loopbacks:
                if normalized_target and normalized_target in _normalize_device_name(device.name):
                    return device
        default_speaker = sc.default_speaker()
        default_name = _normalize_device_name(default_speaker.name)
        for device in loopbacks:
            if default_name and default_name in _normalize_device_name(device.name):
                return device
        return loopbacks[0]

    def _system_loopback_worker(self, loopback: Any) -> None:
        block_frames = max(512, self.samplerate // 10)
        try:
            with loopback.recorder(samplerate=self.samplerate, channels=2, blocksize=block_frames) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=block_frames)
                    mono = self._to_mono_float32(data)
                    with self._lock:
                        self._system_buffer.append(mono)
        except Exception as exc:
            self._report(f"audio_error: system loopback stopped: {exc}")

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


def _normalize_device_name(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())
