"""Legacy page/paragraph alignment preserved for compatibility."""
from __future__ import annotations


def align_paragraphs(amharic_paragraphs: list[str], english_paragraphs: list[str]) -> list[dict[str, str]]:
    """Align Amharic and English paragraphs by index, exactly as the original extractor did."""
    aligned: list[dict[str, str]] = []
    for i in range(max(len(amharic_paragraphs), len(english_paragraphs))):
        aligned.append({
            "amharic": amharic_paragraphs[i] if i < len(amharic_paragraphs) else "",
            "english": english_paragraphs[i] if i < len(english_paragraphs) else "",
        })
    return aligned
