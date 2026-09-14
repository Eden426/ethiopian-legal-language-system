"""OCR provider contracts and an offline Tesseract implementation."""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

SYSTEM_LANGUAGES = frozenset({"amh_Ethi", "eng_Latn"})
TESSERACT_LANGUAGE_PATTERN = re.compile(r"^[a-z]{3}(?:\+[a-z]{3})*$")


class OcrProviderError(RuntimeError):
    """Content-safe failure raised at the external OCR boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OcrResult:
    """Exact text and traceability metadata returned for one page."""

    original_text: str
    mean_confidence: float | None
    engine_name: str
    engine_version: str


class OcrProvider(Protocol):
    """Replaceable provider contract for one rendered page image."""

    def recognize(self, image_path: Path, language: str) -> OcrResult:
        """Extract exact original text using an explicit system language."""


@dataclass(frozen=True)
class TesseractConfig:
    """Validated Tesseract runtime settings loaded from versioned YAML."""

    executable: str
    page_segmentation_mode: int
    timeout_seconds: int
    max_output_characters: int
    amharic_language: str
    english_language: str

    @classmethod
    def from_yaml(cls, path: str | Path) -> TesseractConfig:
        """Load the strict OCR configuration without starting Tesseract."""

        config_path = Path(path)
        with config_path.open(encoding="utf-8") as stream:
            payload = yaml.safe_load(stream)
        if not isinstance(payload, dict):
            raise TypeError("OCR config must be a YAML mapping")
        expected_keys = {
            "schema_version",
            "provider",
            "executable",
            "page_segmentation_mode",
            "timeout_seconds",
            "max_output_characters",
            "languages",
        }
        if set(payload) != expected_keys:
            raise ValueError("OCR config has missing or unknown fields")
        if payload["schema_version"] != 1:
            raise ValueError("Unsupported OCR config schema_version")
        if payload["provider"] != "tesseract":
            raise ValueError("The local OCR config provider must be tesseract")
        languages = payload["languages"]
        if not isinstance(languages, dict) or set(languages) != SYSTEM_LANGUAGES:
            raise ValueError("OCR config must map amh_Ethi and eng_Latn")
        values = (
            payload["executable"],
            languages["amh_Ethi"],
            languages["eng_Latn"],
        )
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("OCR executable and language values must be non-empty strings")
        language_values = (languages["amh_Ethi"], languages["eng_Latn"])
        if any(not TESSERACT_LANGUAGE_PATTERN.fullmatch(value) for value in language_values):
            raise ValueError("Tesseract languages must use three-letter language codes")
        numeric_fields = (
            payload["page_segmentation_mode"],
            payload["timeout_seconds"],
            payload["max_output_characters"],
        )
        if any(isinstance(value, bool) or not isinstance(value, int) for value in numeric_fields):
            raise ValueError("OCR numeric settings must be integers")
        psm, timeout, max_characters = numeric_fields
        if not 1 <= psm <= 13:
            raise ValueError("OCR page_segmentation_mode must be between 1 and 13")
        if not 1 <= timeout <= 3600:
            raise ValueError("OCR timeout_seconds must be between 1 and 3600")
        if not 1 <= max_characters <= 10_000_000:
            raise ValueError("OCR max_output_characters must be between 1 and 10000000")
        return cls(
            executable=payload["executable"],
            page_segmentation_mode=psm,
            timeout_seconds=timeout,
            max_output_characters=max_characters,
            amharic_language=languages["amh_Ethi"],
            english_language=languages["eng_Latn"],
        )

    def provider_language(self, language: str) -> str:
        """Map an explicit system language to its configured Tesseract code."""

        if language == "amh_Ethi":
            return self.amharic_language
        if language == "eng_Latn":
            return self.english_language
        raise OcrProviderError("ocr_language_unsupported", "The OCR language is unsupported.")


def _mean_confidence(tsv_path: Path) -> float | None:
    confidences: list[float] = []
    try:
        with tsv_path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                text = row.get("text", "")
                raw_confidence = row.get("conf", "-1")
                if not text.strip():
                    continue
                try:
                    confidence = float(raw_confidence)
                except ValueError:
                    continue
                if confidence >= 0:
                    confidences.append(min(confidence, 100.0) / 100.0)
    except (OSError, UnicodeError, csv.Error) as error:
        raise OcrProviderError(
            "ocr_output_invalid",
            "The OCR confidence output could not be read.",
        ) from error
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


class TesseractOcrProvider:
    """Offline Tesseract provider with explicit language and resource bounds."""

    def __init__(self, config: TesseractConfig) -> None:
        self.config = config
        self._executable: str | None = None
        self._engine_version: str | None = None

    def _prepare_environment(self) -> tuple[str, str]:
        if self._executable is not None and self._engine_version is not None:
            return self._executable, self._engine_version
        executable = shutil.which(self.config.executable)
        if executable is None:
            raise OcrProviderError(
                "ocr_provider_unavailable",
                "The configured OCR executable is unavailable.",
            )
        try:
            languages = subprocess.run(
                [executable, "--list-langs"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout_seconds,
            )
            version = subprocess.run(
                [executable, "--version"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OcrProviderError(
                "ocr_provider_unavailable",
                "The configured OCR provider could not be inspected.",
            ) from error
        available_languages = set(languages.stdout.splitlines())
        required_languages = {
            self.config.amharic_language,
            self.config.english_language,
        }
        if languages.returncode != 0 or not required_languages <= available_languages:
            raise OcrProviderError(
                "ocr_language_data_missing",
                "The configured OCR language data is unavailable.",
            )
        version_line = version.stdout.splitlines()[0].strip() if version.stdout else ""
        if version.returncode != 0 or not version_line:
            raise OcrProviderError(
                "ocr_provider_unavailable",
                "The configured OCR provider version is unavailable.",
            )
        self._executable = executable
        self._engine_version = version_line[:100]
        return self._executable, self._engine_version

    def recognize(self, image_path: Path, language: str) -> OcrResult:
        """Extract exact UTF-8 text and word-confidence metadata from one PNG."""

        if image_path.suffix.casefold() != ".png" or not image_path.is_file():
            raise OcrProviderError(
                "ocr_page_unavailable",
                "The rendered page image is unavailable.",
            )
        provider_language = self.config.provider_language(language)
        executable, engine_version = self._prepare_environment()
        with tempfile.TemporaryDirectory(prefix="ells-ocr-") as temporary_directory:
            output_base = Path(temporary_directory) / "page"
            command = [
                executable,
                str(image_path),
                str(output_base),
                "-l",
                provider_language,
                "--psm",
                str(self.config.page_segmentation_mode),
                "txt",
                "tsv",
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.config.timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise OcrProviderError(
                    "ocr_timeout",
                    "OCR exceeded the configured per-page time limit.",
                ) from error
            except OSError as error:
                raise OcrProviderError(
                    "ocr_provider_unavailable",
                    "The configured OCR provider could not be started.",
                ) from error
            if completed.returncode != 0:
                raise OcrProviderError(
                    "ocr_page_failed",
                    "The OCR provider could not process a rendered page.",
                )
            text_path = output_base.with_suffix(".txt")
            tsv_path = output_base.with_suffix(".tsv")
            try:
                original_text = text_path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError) as error:
                raise OcrProviderError(
                    "ocr_output_invalid",
                    "The OCR text output could not be read as UTF-8.",
                ) from error
            if len(original_text) > self.config.max_output_characters:
                raise OcrProviderError(
                    "ocr_output_too_large",
                    "OCR output exceeded the configured character limit.",
                )
            return OcrResult(
                original_text=original_text,
                mean_confidence=_mean_confidence(tsv_path),
                engine_name="tesseract",
                engine_version=engine_version,
            )
