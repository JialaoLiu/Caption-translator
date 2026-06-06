from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import shutil
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
    "funasr_server": AsrModelInfo(
        key="funasr_server",
        label="Fun-ASR-Nano local vLLM/FunASR service",
        backend="openai_asr_api",
        repo_id="FunAudioLLM/Fun-ASR-Nano-2512",
        source="server",
        local_dir_name="server",
    ),
    "qwen3_vllm_server": AsrModelInfo(
        key="qwen3_vllm_server",
        label="Qwen3-ASR local vLLM service",
        backend="openai_asr_api",
        repo_id="Qwen/Qwen3-ASR-1.7B",
        source="server",
        local_dir_name="server",
    ),
}


def asr_model_root() -> Path:
    return runtime_root() / "models" / "asr"


def model_local_dir(model_key: str) -> Path:
    info = ASR_MODELS[model_key]
    return asr_model_root() / info.local_dir_name


def is_model_downloaded(model_key: str) -> bool:
    path = model_local_dir(model_key)
    if not path.exists() or not any(path.iterdir()):
        return False
    info = ASR_MODELS[model_key]
    if info.source == "modelscope":
        return any(path.glob("*.bin")) or any(path.glob("*.pt")) or any(path.glob("*.onnx")) or any(path.glob("configuration.json"))
    if info.source == "huggingface":
        return any(path.glob("*.bin")) or any(path.glob("*.safetensors")) or any(path.glob("config.json"))
    return any(path.iterdir())


def download_asr_model(model_key: str, progress: Callable[[int, str], None]) -> Path:
    info = ASR_MODELS[model_key]
    target = model_local_dir(model_key)
    if target.exists() and not is_model_downloaded(model_key):
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    if info.source == "builtin":
        progress(100, "faster-whisper downloads automatically on first use.")
        return target
    if info.source == "server":
        progress(100, "Server mode does not download local ASR weights.")
        return target
    ensure_asr_dependencies(model_key, progress)
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
    if not is_model_downloaded(model_key):
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"Model download did not produce usable files: {info.label}")
    progress(100, f"Downloaded {info.label}.")
    return target


def ensure_asr_dependencies(model_key: str, progress: Callable[[int, str], None]) -> None:
    info = ASR_MODELS[model_key]
    if info.backend == "funasr":
        ensure_python_modules(
            imports=["torch", "torchaudio", "funasr", "modelscope", "soundfile"],
            packages=["torch", "torchaudio", "funasr>=1.2.7", "modelscope>=1.20", "soundfile>=0.12"],
            progress=progress,
        )
    elif info.backend == "qwen3_asr":
        ensure_python_modules(
            imports=["qwen_asr", "huggingface_hub", "torch"],
            packages=["qwen-asr", "huggingface_hub>=0.24", "torch"],
            progress=progress,
        )


def ensure_python_modules(imports: list[str], packages: list[str], progress: Callable[[int, str], None]) -> None:
    missing = []
    for module in imports:
        try:
            __import__(module)
        except Exception:
            missing.append(module)
    if not missing:
        progress(8, "ASR dependencies are ready.")
        return
    progress(8, f"Installing ASR dependencies: {', '.join(packages)}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *packages],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or "Failed to install ASR dependencies.")
    progress(12, "ASR dependencies installed.")
