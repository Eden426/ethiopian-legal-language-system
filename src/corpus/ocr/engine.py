"""OCR provider interface."""
from __future__ import annotations

from typing import Protocol, Any


class OCRProvider(Protocol):
    def image_to_text(self, image: Any, language: str, config: str) -> str:
        ...
