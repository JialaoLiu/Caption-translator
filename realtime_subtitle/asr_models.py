from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .app_config import runtime_root


@dataclass(frozen=True)
class AsrModelInfo:
    key: str
    label: str
    backend: str
    repo_id: str
    source: str
    local_dir_name: str


ASR_MODELS: dict[str, AsrModelInfo] = {
    "faster_whisper_small": AsrModelInfo(
        key="faster_whisper_small",
        label="faster-whisper small (default)",
        backend="faster_whisper",
        repo_id="small",
        source="builtin",
        local_dir_name="faster-whisper-small",
    ),
    "fun_asr_nano": AsrModelInfo(
        key="fun_asr_nano",
        label="Fun-ASR-Nano 2512",
        backend="funasr",
        repo_id="FunAudioLLM/Fun-ASR-Nano-2512",
        source="huggingface",
        local_dir_name="Fun-ASR-Nano-2512",
    ),
    "sensevoice_small": AsrModelInfo(
        key="sensevoice_small",
        label="SenseVoiceSmall 234M (default)",
        backend="funasr",
        repo_id="iic/SenseVoiceSmall",
        source="modelscope",
        local_dir_name="SenseVoiceSmall",
    ),
    "qwen3_asr_0_6b": AsrModelInfo(
        key="qwen3_asr_0_6b",
        label="Qwen3-ASR-0.6B",
        backend="qwen3_asr",
        repo_id="Qwen/Qwen3-ASR-0.6B",
        source="huggingface",
        local_dir_name="Qwen3-ASR-0.6B",
    ),
    "qwen3_asr_1_7b": AsrModelInfo(
        key="qwen3_asr_1_7b",
        label="Qwen3-ASR-1.7B",
        backend="qwen3_asr",
        repo_id="Qwen/Qwen3-ASR-1.7B",
        source="huggingface",
        local_dir_name="Qwen3-ASR-1.7B",
    ),
}


def asr_model_root() -> Path:
    return runtime_root() / "models" / "asr"


def model_local_dir(model_key: str) -> Path:
    info = ASR_MODELS[model_key]
    return asr_model_root() / info.local_dir_name


def is_model_downloaded(model_key: str) -> bool:
    path = model_local_dir(model_key)
    return path.exists() and any(path.iterdir())


def download_asr_model(model_key: str, progress: Callable[[int, str], None]) -> Path:
    info = ASR_MODELS[model_key]
    target = model_local_dir(model_key)
    target.mkdir(parents=True, exist_ok=True)
    if info.source == "builtin":
        progress(100, "faster-whisper downloads automatically on first use.")
        return target
    progress(5, f"Preparing {info.label}...")
    if info.source == "huggingface":
        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:
            raise RuntimeError("Missing dependency: pip install huggingface_hub") from exc
        progress(15, f"Downloading {info.repo_id} from Hugging Face...")
        snapshot_download(
            repo_id=info.repo_id,
            local_dir=str(target),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
    elif info.source == "modelscope":
        try:
            from modelscope import snapshot_download
        except Exception as exc:
            raise RuntimeError("Missing dependency: pip install modelscope") from exc
        progress(20, f"Downloading {info.repo_id} from ModelScope. This can take a while...")
        snapshot_download(info.repo_id, local_dir=str(target))
    else:
        raise RuntimeError(f"Unsupported model source: {info.source}")
    progress(100, f"Downloaded {info.label}.")
    return target
