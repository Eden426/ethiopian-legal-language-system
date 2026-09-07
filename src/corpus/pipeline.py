"""End-to-end Negarit Gazeta PDF extraction pipeline."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tqdm import tqdm

from src.corpus.config import CorpusConfig
from src.corpus.ingestion.pdf import pdf_to_images
from src.corpus.ocr.tesseract import (
    crop_first_page_title,
    ocr_image,
    preprocess_image,
    remove_boxes_from_image,
    remove_header_footer,
    split_columns,
)
from src.corpus.normalization.text import (
    clean_text,
    is_valid_amharic_line,
    merge_paragraphs,
    recover_ethiopic_numerals,
    remove_closing_section,
    split_paragraphs,
)
from src.corpus.export.json_export import write_legacy_json


def extract_pdf_to_json(pdf_path: Path, output_file: Path, config: CorpusConfig, logger: logging.Logger) -> bool:
    results: list[dict[str, Any]] = []
    for page_number, img, total_pages in tqdm(pdf_to_images(pdf_path, config), desc=f"OCR {pdf_path.name}", unit="page"):
        try:
            if page_number == 1:
                img = crop_first_page_title(img, config)
            else:
                img = remove_header_footer(img, config)
            img = remove_boxes_from_image(img)
            img = preprocess_image(img)

            if page_number == total_pages:
                width, height = img.size
                fixed_split_x = int(width * 0.51)
                left_img = img.crop((0, 0, fixed_split_x, height))
                right_img = img.crop((fixed_split_x, 0, width, height))
            else:
                left_img, right_img = split_columns(img)

            am_text = ocr_image(image=left_img, language=config.amharic_language, ocr_config=config.amharic_config)
            en_text = ocr_image(image=right_img, language=config.english_language, ocr_config=config.english_config)

            am_text = recover_ethiopic_numerals(clean_text(am_text))
            en_text = clean_text(en_text)

            if page_number == total_pages:
                am_text = remove_closing_section(am_text)
                en_text = remove_closing_section(en_text)

            am_paragraphs = [p for p in split_paragraphs(am_text) if is_valid_amharic_line(p)]
            en_paragraphs = split_paragraphs(en_text)

            results.append({
                "page_number": page_number,
                "amharic": merge_paragraphs(am_paragraphs),
                "english": merge_paragraphs(en_paragraphs),
            })
        except Exception as exc:
            logger.exception("Error processing page %d of %s", page_number, pdf_path.name)
            results.append({"page_number": page_number, "amharic": "", "english": ""})

    write_legacy_json(results, output_file)
    logger.info("Saved %s (%d pages)", output_file, len(results))
    return True
