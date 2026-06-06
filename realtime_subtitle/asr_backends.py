from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Protocol
from urllib import request
from urllib.error import HTTPError, URLError

import numpy as np
from faster_whisper import WhisperModel

from .asr_models import ASR_MODELS, is_model_downloaded, model_local_dir


LANGUAGE_MAP = {
    "auto": None,
    "yue": "zh",
    "zh": "zh",
    "en": "en",
}


class AsrBackend(Protocol):
    def transcribe(self, audio: np.ndarray, source_language: str) -> str:
        ...


class FasterWhisperBackend:
    def __init__(
        self,
        model_size: str,
        device: str,
        compute_type: str,
        beam_size: int,
        vad_filter: bool,
        no_speech_threshold: float,
        condition_on_previous_text: bool,
    ) -> None:
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.no_speech_threshold = no_speech_threshold
        self.condition_on_previous_text = condition_on_previous_text
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, source_language: str) -> str:
        segments, _info = self.model.transcribe(
            audio,
            language=LANGUAGE_MAP.get(source_language),
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
            no_speech_threshold=self.no_speech_threshold,
            condition_on_previous_text=self.condition_on_previous_text,
            without_timestamps=True,
        )
        return "".join(segment.text for segment in segments).strip()


class FunAsrBackend:
    def __init__(self, model_key: str, device: str) -> None:
        try:
            from funasr import AutoModel
        except Exception as exc:
            raise RuntimeError("Missing dependency: pip install funasr modelscope soundfile") from exc
        self.model_key = model_key
        info = ASR_MODELS[model_key]
        model_path = str(model_local_dir(model_key)) if is_model_downloaded(model_key) else info.repo_id
        kwargs = {"model": model_path, "trust_remote_code": True, "device": "cuda:0" if device == "cuda" else "cpu"}
        if model_key == "sensevoice_small":
            kwargs["disable_update"] = True
        self.model = AutoModel(**kwargs)

    def transcribe(self, audio: np.ndarray, source_language: str) -> str:
        wav_path = write_temp_wav(audio)
        try:
            kwargs = {"input": [wav_path], "cache": {}, "batch_size": 1}
            if self.model_key == "fun_asr_nano":
                kwargs["language"] = funasr_language(source_language)
                kwargs["itn"] = True
            result = self.model.generate(**kwargs)
            if not result:
                return ""
            first = result[0]
            if isinstance(first, dict):
                return clean_asr_text(str(first.get("text", "")))
            return clean_asr_text(str(first))
        finally:
            Path(wav_path).unlink(missing_ok=True)


class Qwen3AsrBackend:
    def __init__(self, model_key: str, device: str) -> None:
        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except Exception as exc:
            raise RuntimeError("Missing dependency: pip install qwen-asr torch") from exc
        info = ASR_MODELS[model_key]
        model_path = str(model_local_dir(model_key)) if is_model_downloaded(model_key) else info.repo_id
        kwargs = {
            "dtype": torch.float16 if device == "cuda" else torch.float32,
            "device_map": "cuda:0" if device == "cuda" else "cpu",
            "max_inference_batch_size": 1,
            "max_new_tokens": 256,
        }
        self.model = Qwen3ASRModel.from_pretrained(model_path, **kwargs)

    def transcribe(self, audio: np.ndarray, source_language: str) -> str:
        language = qwen_language(source_language)
        result = self.model.transcribe(audio=(audio, 16000), language=language)
        if not result:
            return ""
        return clean_asr_text(str(getattr(result[0], "text", "")))


class OpenAICompatibleAsrBackend:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = (base_url or "http://127.0.0.1:8000/v1").rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip() or "sensevoice"

    def transcribe(self, audio: np.ndarray, source_language: str) -> str:
        wav_path = write_temp_wav(audio)
        try:
            fields = {"model": self.model}
            language = api_language(source_language)
            if language:
                fields["language"] = language
            body, content_type = build_multipart(fields, "file", "audio.wav", Path(wav_path).read_bytes())
            headers = {"Content-Type": content_type}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = request.Request(
                f"{self.base_url}/audio/transcriptions",
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=120) as response:
                    payload = response.read().decode("utf-8", errors="replace")
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"ASR API error {exc.code}: {detail}") from exc
            except URLError as exc:
                raise RuntimeError(f"ASR API unavailable: {exc.reason}") from exc
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return payload.strip()
            if isinstance(data, dict):
                text = data.get("text") or data.get("transcription")
                if text is not None:
                    return clean_asr_text(str(text))
                choices = data.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    message = choices[0].get("message", {})
                    if isinstance(message, dict) and message.get("content"):
                        return clean_asr_text(str(message["content"]))
            return clean_asr_text(str(data))
        finally:
            Path(wav_path).unlink(missing_ok=True)


def write_temp_wav(audio: np.ndarray) -> str:
    try:
        import soundfile as sf
    except Exception as exc:
        raise RuntimeError("Missing dependency: pip install soundfile") from exc
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp.close()
    sf.write(temp.name, audio, 16000)
    return temp.name


def funasr_language(source_language: str) -> str:
    return {
        "auto": "auto",
        "yue": "yue",
        "zh": "zh",
        "en": "en",
    }.get(source_language, "auto")


def qwen_language(source_language: str) -> str | None:
    return {
        "auto": None,
        "yue": "Cantonese",
        "zh": "Chinese",
        "en": "English",
    }.get(source_language)


def api_language(source_language: str) -> str | None:
    return {
        "auto": None,
        "yue": "yue",
        "zh": "zh",
        "en": "en",
    }.get(source_language)


def build_multipart(fields: dict[str, str], file_field: str, filename: str, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = "caption-translator-boundary"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("ascii"),
            b"Content-Type: audio/wav\r\n\r\n",
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def clean_asr_text(text: str) -> str:
    cleaned = re.sub(r"<\|[^|]+?\|>", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
