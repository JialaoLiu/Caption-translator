from __future__ import annotations

import re

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover - dependency may be absent in source-only checks
    OpenCC = None  # type: ignore[assignment]


_T2S = OpenCC("t2s") if OpenCC else None
_S2T = OpenCC("s2t") if OpenCC else None

CANTONESE_PARTICLE_PATTERN = re.compile(
    r"(咩|咋|啫|吖|喎|噃|啦|喇|啰|囉|呀|啊|嘅|哋|咗|嗰|乜|冇|嚟|啱|唔|嚿)"
)

COMMON_CANTONESE_TO_MANDARIN = {
    "今日": "今天",
    "食": "吃",
    "飯": "饭",
    "未": "了没有",
    "冇": "没有",
    "唔": "不",
    "佢": "他",
    "哋": "们",
    "啱啱": "刚刚",
    "同我講": "跟我说",
    "無問題": "没有问题",
    "無": "没有",
    "睇一睇": "看一下",
    "幫我": "帮我",
    "等陣": "等一下",
    "去邊度": "去哪里",
}


def traditional_to_simplified(text: str) -> str:
    if _T2S:
        return _T2S.convert(text)
    return text


def simplified_to_traditional(text: str) -> str:
    if _S2T:
        return _S2T.convert(text)
    return text


def clean_cantonese_particles(text: str) -> str:
    return CANTONESE_PARTICLE_PATTERN.sub("", text)


def light_cantonese_to_mandarin(text: str) -> str:
    normalized = traditional_to_simplified(text)
    for source, target in COMMON_CANTONESE_TO_MANDARIN.items():
        normalized = normalized.replace(traditional_to_simplified(source), traditional_to_simplified(target))
    normalized = clean_cantonese_particles(normalized)
    normalized = normalized.replace("你今天吃饭了没有", "你今天吃饭了没有")
    return normalized


def normalize_for_target_language(text: str, target_language: str, source_language: str = "auto") -> str:
    normalized = text.strip().strip("\"'")
    if target_language == "zh_hans":
        normalized = traditional_to_simplified(normalized)
        if source_language == "yue":
            normalized = light_cantonese_to_mandarin(normalized)
        return normalized
    if target_language == "zh_hant":
        return simplified_to_traditional(normalized)
    return normalized
