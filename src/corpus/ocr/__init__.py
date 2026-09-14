"""Replaceable, language-aware OCR for rendered corpus pages."""

from src.corpus.ocr.providers import (
    OcrProvider,
    OcrProviderError,
    OcrResult,
    TesseractConfig,
    TesseractOcrProvider,
)
from src.corpus.ocr.service import process_ocr_job, run_job_ocr

__all__ = [
    "OcrProvider",
    "OcrProviderError",
    "OcrResult",
    "TesseractConfig",
    "TesseractOcrProvider",
    "process_ocr_job",
    "run_job_ocr",
]
