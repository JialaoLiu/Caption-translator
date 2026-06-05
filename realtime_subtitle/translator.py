from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


LANGUAGE_NAMES = {
    "auto": "auto detected language",
    "yue": "Cantonese",
    "zh": "Mandarin Chinese",
    "en": "English",
}


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source_language: str
    target_language: str


class BaseTranslator:
    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError


class MockTranslator(BaseTranslator):
    def translate(self, request: TranslationRequest) -> str:
        text = request.text.strip()
        if not text:
            return ""
        if request.source_language == request.target_language:
            return text
        return f"[{request.target_language}] {text}"


class OllamaTranslator(BaseTranslator):
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
                "temperature": 0.2,
                "num_predict": 90,
            },
        }
        data = http_json(
            f"{self.base_url}/api/generate",
            payload=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )
        return str(data.get("response", "")).strip()


class OpenAICompatibleTranslator(BaseTranslator):
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
                {
                    "role": "system",
                    "content": "You translate short live-stream subtitles. Keep it brief, casual, and natural. Return only the translation.",
                },
                {"role": "user", "content": build_translation_prompt(request)},
            ],
            "temperature": 0.2,
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
        return str(message.get("content", "")).strip()


def build_translation_prompt(request: TranslationRequest) -> str:
    source = LANGUAGE_NAMES.get(request.source_language, request.source_language)
    target = LANGUAGE_NAMES.get(request.target_language, request.target_language)
    return (
        f"Translate this live subtitle from {source} to {target}.\n"
        "Style: short, spoken, casual, suitable for gaming livestream subtitles.\n"
        "Do not add explanations, labels, brackets, or extra commentary.\n\n"
        f"Text:\n{request.text.strip()}"
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
