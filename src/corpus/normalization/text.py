"""Non-destructive text cleanup and legacy normalization rules."""
from __future__ import annotations

import re


def clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    patterns = [
        r"FEDERAL NEGARIT GAZETA.*",
        r"Federal Negarit Gazeta.*",
        r"Negarit G\.?P\.?O\.?Box.*",
        r"Unit Price.*",
        r"ADDIS ABABA.*",
        r"Page\s*\d+",
        r"ፌዴራል.*ጋዜጣ.*",
        r"ገጽ\s*[0-9፩-፺]+",
        r"ፌዶዕራል ሃፃ2ፖ*",
        r"ያንዱ ዋጋ.*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    allowed_pattern = r"[^A-Za-z0-9\u1200-\u137F\s\.\,\;\:\?\!\(\)/፡።፣፤፥፦\-]"
    text = re.sub(allowed_pattern, "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def is_valid_amharic_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    ethiopic = re.findall(r"[\u1200-\u137F]", stripped)
    ratio = len(ethiopic) / max(len(stripped), 1)
    if ratio < 0.20:
        return False
    if re.search(r"[^\u1200-\u137F0-9\s፡።፣፤፥፦:\.\-\(\)/]", stripped):
        return False
    return True


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 1]


def remove_closing_section(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        normalized = line.lower().strip()
        if re.match(r"d[o0]ne\s+a?t", normalized):
            break
        if re.search(r"አዲስ\s*አበባ.*ቀን", line):
            break
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def recover_ethiopic_numerals(text: str) -> str:
    for digit, numeral in zip("123456789", "፩፪፫፬፭፮፯፰፱"):
        text = re.sub(rf"\b{digit}\b", numeral, text)
    for wrong, correct in {"፳፩": "፲፩", "፳፪": "፲፪", "፳፫": "፲፫"}.items():
        text = text.replace(wrong, correct)
    text = re.sub(r"(?<=ቁጥር\s)፳(?=\s)", "፪", text)
    text = re.sub(r"(?<=አንቀጽ\s)፳(?=\s)", "፪", text)
    return text


def merge_paragraphs(paragraphs: list[str]) -> str:
    return " ".join(paragraphs).strip()
