from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol

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
                return str(first.get("text", "")).strip()
            return str(first).strip()
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
        return str(getattr(result[0], "text", "")).strip()


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
        "yue": "粤语",
        "zh": "中文",
        "en": "英文",
    }.get(source_language, "auto")


def qwen_language(source_language: str) -> str | None:
    return {
        "auto": None,
        "yue": "Cantonese",
        "zh": "Chinese",
        "en": "English",
    }.get(source_language)
