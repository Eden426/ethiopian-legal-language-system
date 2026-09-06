"""Tesseract OCR and image preparation, migrated from the original extractor."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
from PIL import Image

from src.corpus.config import CorpusConfig


def find_tesseract(config: CorpusConfig) -> str | None:
    if config.tesseract_path:
        path = Path(config.tesseract_path)
        if path.exists():
            return str(path)
    env_path = os.environ.get("TESSERACT_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    found = shutil.which("tesseract")
    if found:
        return found
    common = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for path in common:
        if path.exists():
            return str(path)
    return None


def find_poppler(config: CorpusConfig) -> str | None:
    if config.poppler_path and Path(config.poppler_path).exists():
        return str(config.poppler_path)
    env_path = os.environ.get("POPPLER_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    if shutil.which("pdfinfo") and shutil.which("pdftoppm"):
        return None
    for path in (
        Path(r"C:\poppler\Library\bin"),
        Path(r"C:\Program Files\poppler\Library\bin"),
        Path(r"C:\Program Files\poppler\bin"),
        Path(r"C:\poppler\bin"),
    ):
        if path.exists():
            return str(path)
    return None


def validate_environment(config: CorpusConfig) -> tuple[str, str | None]:
    tesseract = find_tesseract(config)
    if not tesseract:
        raise RuntimeError("Tesseract OCR was not found. Install it or set TESSERACT_PATH.")
    pytesseract.pytesseract.tesseract_cmd = tesseract
    languages = pytesseract.get_languages(config="")
    if config.amharic_language not in languages:
        raise RuntimeError(f"Tesseract language data '{config.amharic_language}' was not found.")
    poppler = find_poppler(config)
    if not poppler and not (shutil.which("pdfinfo") and shutil.which("pdftoppm")):
        raise RuntimeError("Poppler was not found. Install it or set POPPLER_PATH.")
    return tesseract, poppler


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    img = np.array(pil_image)
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img
    gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=10)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return Image.fromarray(gray)


def remove_boxes_from_image(pil_image: Image.Image) -> Image.Image:
    img = np.array(pil_image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            x, y, w, h = cv2.boundingRect(approx)
            if w > 100 and h > 30:
                fill = (255, 255, 255) if len(img.shape) == 3 else 255
                cv2.drawContours(img, [approx], -1, fill, -1)
    return Image.fromarray(img)


def remove_header_footer(image: Image.Image, config: CorpusConfig) -> Image.Image:
    width, height = image.size
    top = int(height * config.top_crop_ratio)
    bottom = int(height * (1 - config.bottom_crop_ratio))
    return image.crop((0, top, width, bottom))


def crop_first_page_title(image: Image.Image, config: CorpusConfig) -> Image.Image:
    width, height = image.size
    top = int(height * config.first_page_title_ratio)
    return image.crop((0, top, width, height))


def detect_column_split(image: Image.Image) -> int:
    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    gray = gray[int(h * 0.20):, :]
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    vertical_sum = np.sum(binary, axis=0)
    center = w // 2
    search_window = int(w * 0.10)
    start, end = center - search_window, center + search_window
    vertical_sum = cv2.GaussianBlur(vertical_sum.astype(np.float32), (31, 1), 0).flatten()
    return int(start + np.argmin(vertical_sum[start:end]))


def split_columns(image: Image.Image) -> tuple[Image.Image, Image.Image]:
    width, height = image.size
    split_x = detect_column_split(image)
    left = image.crop((0, 0, split_x + 20, height))
    right = image.crop((max(split_x - 20, 0), 0, width, height))
    return left, right


def ocr_image(image: Image.Image, language: str, ocr_config: str) -> str:
    return pytesseract.image_to_string(image, lang=language, config=ocr_config)
