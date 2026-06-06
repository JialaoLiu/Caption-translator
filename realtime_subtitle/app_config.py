from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_NAME = "Caption translator"
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


DEFAULT_CONFIG: dict[str, Any] = {
    "audio_device": None,
    "system_audio_device": None,
    "audio_mode": "mic_plus_system",
    "model_size": "small",
    "asr_backend": "funasr",
    "asr_model_key": "sensevoice_small",
    "device": "cpu",
    "compute_type": "int8",
    "source_language": "auto",
    "target_language": "zh_hans",
    "display_mode": "translation",
    "app_language": "zh_CN",
    "accuracy_mode": "balanced",
    "beam_size": 5,
    "vad_filter": True,
    "no_speech_threshold": 0.6,
    "condition_on_previous_text": False,
    "translator_backend": "ollama",
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5:3b",
    },
    "openai_compatible": {
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "",
        "model": "qwen2.5-3b",
    },
    "asr_api": {
        "base_url": "http://127.0.0.1:8000/v1",
        "api_key": "",
        "model": "FunAudioLLM/Fun-ASR-Nano-2512",
    },
    "chunk_seconds": 3.0,
    "font_size": 32,
    "font_family": "Microsoft YaHei UI",
    "font_color": "#ffffff",
    "opacity": 0.82,
    "background_color": "#000000",
    "show_border": False,
    "pinned": True,
    "line_mode": "auto",
    "max_chars": 120,
    "word_wrap": True,
    "subtitle_output": "subtitle.txt",
    "subtitle_window": {
        "x": 160,
        "y": 80,
        "width": 920,
        "height": 150,
    },
}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def user_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", runtime_root()))
        return base / "CaptionTranslator"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CaptionTranslator"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "caption-translator"


def config_path() -> Path:
    override = os.environ.get("WPS_CONFIG")
    if override:
        return Path(override)
    local_config = runtime_root() / "config.json"
    if local_config.exists() or not is_frozen():
        return local_config
    return user_config_dir() / "config.json"


def subtitle_output_path(config: dict[str, Any]) -> Path:
    configured = Path(str(config.get("subtitle_output", "subtitle.txt")))
    if configured.is_absolute():
        return configured
    return runtime_root() / configured


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        config = deepcopy(DEFAULT_CONFIG)
        save_config(config)
        return config
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("config root must be an object")
        return merge_defaults(loaded)
    except Exception:
        backup = path.with_suffix(".broken.json")
        try:
            path.replace(backup)
        except OSError:
            pass
        config = deepcopy(DEFAULT_CONFIG)
        save_config(config)
        return config


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merge_defaults(config), ensure_ascii=False, indent=2), encoding="utf-8")


def merge_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    _deep_update(merged, config)
    return merged


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
