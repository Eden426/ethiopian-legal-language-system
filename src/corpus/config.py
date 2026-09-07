"""Configuration loading for the corpus pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

import yaml


@dataclass(frozen=True)
class CorpusConfig:
    root: Path
    input_dir: Path
    working_dir: Path
    pages_dir: Path
    ocr_dir: Path
    output_dir: Path
    log_dir: Path
    tesseract_path: str | None
    poppler_path: str | None
    amharic_language: str
    english_language: str
    amharic_config: str
    english_config: str
    ocr_dpi: int
    top_crop_ratio: float
    bottom_crop_ratio: float
    first_page_title_ratio: float
    overwrite_output: bool
    sort_input_files: bool
    save_page_images: bool
    write_manifest: bool

    def ensure_directories(self) -> None:
        for path in (
            self.input_dir,
            self.working_dir,
            self.pages_dir,
            self.ocr_dir,
            self.output_dir,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _resolve(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def load_config(path: Path | None = None) -> CorpusConfig:
    root = Path(__file__).resolve().parents[2]
    config_path = path or root / "configs" / "corpus.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}

    paths = data.get("paths", {})
    tess = data.get("tesseract", {})
    poppler = data.get("poppler", {})
    ocr = data.get("ocr", {})
    image = data.get("image", {})
    processing = data.get("processing", {})
    output = data.get("output", {})

    tesseract_env = os.environ.get("TESSERACT_PATH")
    poppler_env = os.environ.get("POPPLER_PATH")

    cfg = CorpusConfig(
        root=root,
        input_dir=_resolve(root, paths.get("input_dir", "data/corpus/input")) or root / "data/corpus/input",
        working_dir=_resolve(root, paths.get("working_dir", "data/corpus/working")) or root / "data/corpus/working",
        pages_dir=_resolve(root, paths.get("pages_dir", "data/corpus/pages")) or root / "data/corpus/pages",
        ocr_dir=_resolve(root, paths.get("ocr_dir", "data/corpus/ocr")) or root / "data/corpus/ocr",
        output_dir=_resolve(root, paths.get("output_dir", "data/corpus/exports")) or root / "data/corpus/exports",
        log_dir=_resolve(root, paths.get("log_dir", "artifacts/corpus_logs")) or root / "artifacts/corpus_logs",
        tesseract_path=tesseract_env or tess.get("path"),
        poppler_path=poppler_env or poppler.get("path"),
        amharic_language=tess.get("amharic_language", "amh"),
        english_language=tess.get("english_language", "eng"),
        amharic_config=tess.get("amharic_config", "--oem 1 --psm 4 -c preserve_interword_spaces=1"),
        english_config=tess.get("english_config", "--oem 3 --psm 4"),
        ocr_dpi=int(ocr.get("dpi", 400)),
        top_crop_ratio=float(image.get("top_crop_ratio", 0.05)),
        bottom_crop_ratio=float(image.get("bottom_crop_ratio", 0.08)),
        first_page_title_ratio=float(image.get("first_page_title_ratio", 0.38)),
        overwrite_output=bool(processing.get("overwrite_output", True)),
        sort_input_files=bool(processing.get("sort_input_files", True)),
        save_page_images=bool(processing.get("save_page_images", False)),
        write_manifest=bool(output.get("write_manifest", True)),
    )
    cfg.ensure_directories()
    return cfg
