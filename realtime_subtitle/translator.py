from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .text_normalizer import normalize_for_target_language


LANGUAGE_NAMES = {
    "auto": "auto detected language",
    "yue": "Cantonese",
    "zh": "Mandarin",
    "zh_hans": "Mandarin Simplified Chinese",
    "zh_hant": "Mandarin Traditional Chinese",
    "en": "English",
}


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source_language: str
    target_language: str


class BaseTranslator:
    real_translation = False

    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError


class MockTranslator(BaseTranslator):
    real_translation = False

    def translate(self, request: TranslationRequest) -> str:
        text = request.text.strip()
        if not text:
            return ""
        if request.source_language == request.target_language:
            return normalize_for_target_language(text, request.target_language, request.source_language)
        return normalize_for_target_language(f"[{request.target_language}] {text}", request.target_language, request.source_language)


class OllamaTranslator(BaseTranslator):
    real_translation = True

    def __init__(self, base_url: str, model: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def translate(self, request: TranslationRequest) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "prompt": build_translation_prompt(request),
            "options": {
                "temperature": 0.15,
                "num_predict": 90,
            },
        }
        data = http_json(
            f"{self.base_url}/api/generate",
            payload=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        return normalize_for_target_language(
            str(data.get("response", "")),
            request.target_language,
            request.source_language,
        )


class OpenAICompatibleTranslator(BaseTranslator):
    real_translation = True

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 25.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def translate(self, request: TranslationRequest) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt_for_target(request.target_language)},
                {"role": "user", "content": build_translation_prompt(request)},
            ],
            "temperature": 0.15,
            "max_tokens": 120,
        }
        data = http_json(
            f"{self.base_url}/chat/completions",
            payload=payload,
            headers=headers,
            timeout=self.timeout,
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return normalize_for_target_language(
            str(message.get("content", "")),
            request.target_language,
            request.source_language,
        )


def system_prompt_for_target(target_language: str) -> str:
    if target_language == "zh_hans":
        return (
            "You convert live subtitles into natural spoken Simplified Mandarin Chinese. "
            "Return only the subtitle text. No explanations, no quotes, no labels."
        )
    if target_language == "zh_hant":
        return (
            "You convert live subtitles into natural spoken Traditional Chinese. "
            "Return only the subtitle text. No explanations, no quotes, no labels."
        )
    if target_language == "yue":
        return (
            "You translate live subtitles into natural spoken Cantonese. "
            "Return only the subtitle text. No explanations, no quotes, no labels."
        )
    return (
        "You translate short gaming livestream subtitles into casual spoken English. "
        "Return only the subtitle text. No explanations, no quotes, no labels."
    )


def build_translation_prompt(request: TranslationRequest) -> str:
    text = request.text.strip()
    source = LANGUAGE_NAMES.get(request.source_language, request.source_language)
    target = LANGUAGE_NAMES.get(request.target_language, request.target_language)
    if request.target_language == "zh_hans":
        return (
            f"Task: convert this live subtitle from {source} to natural spoken Simplified Mandarin Chinese.\n"
            "Rules:\n"
            "- Output Simplified Chinese only.\n"
            "- If the source is Cantonese, convert the meaning and speaking style into natural Mandarin; do not merely convert Traditional to Simplified.\n"
            "- Do not keep Cantonese particles or Cantonese sentence patterns, such as 咩, 咗, 冇, 唔, 嘅, 哋, 喎, 啫, 啱, 嚟, 吖, 啦.\n"
            "- Keep it short and casual for realtime livestream subtitles.\n"
            "- Do not explain, label, quote, or add extra content.\n\n"
            "Examples:\n"
            "Input: 你今日食咗飯未呀？\n"
            "Output: 你今天吃饭了没有？\n"
            "Input: 我哋等陣去邊度呀？\n"
            "Output: 我们等一下去哪里？\n"
            "Input: 佢啱啱同我講冇問題。\n"
            "Output: 他刚刚跟我说没有问题。\n"
            "Input: 唔該你幫我睇一睇。\n"
            "Output: 麻烦你帮我看一下。\n\n"
            f"Input: {text}\n"
            "Output:"
        )
    if request.target_language == "zh_hant":
        return (
            f"Translate this live subtitle from {source} to natural spoken Traditional Chinese.\n"
            "Keep it short, casual, and suitable for livestream subtitles. Return only the subtitle text.\n\n"
            f"Text: {text}"
        )
    if request.target_language == "yue":
        return (
            f"Translate this live subtitle from {source} to natural spoken Cantonese.\n"
            "Keep it short and conversational. Return only the subtitle text.\n\n"
            f"Text: {text}"
        )
    return (
        f"Translate this live subtitle from {source} to {target}.\n"
        "Keep it short, casual, and suitable for gaming livestream subtitles. Return only the subtitle text.\n\n"
        f"Text: {text}"
    )


def http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Translation API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Translation API unavailable: {exc.reason}") from exc


def create_translator(config: dict[str, Any]) -> BaseTranslator:
    kind = str(config.get("translator_backend", "mock")).lower()
    if kind == "mock":
        return MockTranslator()
    if kind == "ollama":
        ollama = config.get("ollama", {})
        return OllamaTranslator(
            base_url=str(ollama.get("base_url", "http://127.0.0.1:11434")),
            model=str(ollama.get("model", "qwen2.5:3b")),
        )
    if kind in {"openai", "openai-compatible", "openai_compatible"}:
        openai_config = config.get("openai_compatible", {})
        return OpenAICompatibleTranslator(
            base_url=str(openai_config.get("base_url", "http://127.0.0.1:8000/v1")),
            api_key=str(openai_config.get("api_key", "")),
            model=str(openai_config.get("model", "qwen2.5-3b")),
        )
    raise ValueError(f"Unsupported translator backend: {kind}")
