from __future__ import annotations

from pathlib import Path


class SubtitleTextOutput:
    def __init__(self, output_path: str | Path) -> None:
        self.output_path = Path(output_path)

    def write(self, text: str) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(text, encoding="utf-8")
