"""PDF discovery and memory-efficient page rendering."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from pdf2image import convert_from_path, pdfinfo_from_path

from src.corpus.config import CorpusConfig


def find_pdf_files(config: CorpusConfig) -> list[Path]:
    files = [p for p in config.input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    if config.sort_input_files:
        files.sort(key=lambda p: p.name.lower())
    return files


def pdf_to_images(pdf_path: Path, config: CorpusConfig) -> Iterator[tuple[int, Any, int]]:
    """Yield one rendered page at a time to avoid loading the whole PDF."""
    info_kwargs: dict[str, Any] = {}
    if config.poppler_path:
        info_kwargs["poppler_path"] = config.poppler_path
    info = pdfinfo_from_path(str(pdf_path), **info_kwargs)
    total_pages = int(info["Pages"])

    for page in range(1, total_pages + 1):
        convert_kwargs: dict[str, Any] = {
            "dpi": config.ocr_dpi,
            "first_page": page,
            "last_page": page,
        }
        if config.poppler_path:
            convert_kwargs["poppler_path"] = config.poppler_path
        images = convert_from_path(str(pdf_path), **convert_kwargs)
        if not images:
            raise RuntimeError(f"Could not render page {page} of {pdf_path}")
        yield page, images[0], total_pages
