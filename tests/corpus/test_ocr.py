from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterable
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter

from src.common.artifact_storage import ArtifactStorage, ArtifactStorageConfig
from src.common.job_store import JobState, JobStore
from src.corpus.ingestion.rendering import RenderedPage, render_job_pages
from src.corpus.ingestion.uploads import UploadLimits, store_upload_pair
from src.corpus.ocr import (
    OcrProviderError,
    OcrResult,
    TesseractConfig,
    TesseractOcrProvider,
    process_ocr_job,
    run_job_ocr,
)

CONFIG_PATH = Path(__file__).parents[2] / "configs" / "ocr.yaml"


def _pdf_bytes(width: int) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=300)
    writer.write(output)
    return output.getvalue()


class SyntheticRenderer:
    def render(self, pdf_path: Path, expected_pages: int) -> Iterable[RenderedPage]:
        assert expected_pages == 1
        marker = b"source" if pdf_path.stem == "source" else b"target"
        yield RenderedPage(1, b"\x89PNG\r\n\x1a\n" + marker, 100, 200)


def _rendered_job(tmp_path: Path) -> tuple[str, JobStore, ArtifactStorage]:
    store = JobStore(tmp_path / "ells.db")
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private"))
    job = store.create(law_type="book", title="Synthetic OCR fixture")
    store_upload_pair(
        job_id=job.id,
        source_file=BytesIO(_pdf_bytes(100)),
        source_filename="source.pdf",
        source_content_type="application/pdf",
        target_file=BytesIO(_pdf_bytes(101)),
        target_filename="target.pdf",
        target_content_type="application/pdf",
        storage=storage,
        store=store,
        limits=UploadLimits(max_pdf_bytes=1024 * 1024, max_pdf_pages=10),
    )
    store.transition(
        job.id,
        JobState.QUEUED,
        stage="page_rendering_queued",
        progress=0.0,
    )
    render_job_pages(job.id, storage=storage, store=store, renderer=SyntheticRenderer())
    return job.id, store, storage


class ExactBilingualProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.texts = {
            "amh_Ethi": "  አንቀጽ ፩።\nግዴታ አይደለም።\n",
            "eng_Latn": "  Article 1.\nIt is not mandatory.\n",
        }

    def recognize(self, _: Path, language: str) -> OcrResult:
        self.calls.append(language)
        return OcrResult(
            original_text=self.texts[language],
            mean_confidence=0.875,
            engine_name="contract-fixture",
            engine_version="1.0",
        )


def test_ocr_contract_preserves_exact_bilingual_text_and_provenance(tmp_path: Path) -> None:
    job_id, store, storage = _rendered_job(tmp_path)
    provider = ExactBilingualProvider()

    job = run_job_ocr(job_id, storage=storage, store=store, provider=provider)

    records = store.list_ocr_pages(job_id)
    rendered_pages = store.list_pages(job_id)
    assert job.state is JobState.PROCESSING
    assert job.stage == "ocr_complete"
    assert job.progress == 1.0
    assert provider.calls == ["amh_Ethi", "eng_Latn"]
    assert [(record.role, record.language, record.page_number) for record in records] == [
        ("source", "amh_Ethi", 1),
        ("target", "eng_Latn", 1),
    ]
    for record, page in zip(records, rendered_pages, strict=True):
        expected_text = provider.texts[record.language]
        content = storage.ocr_path(job_id, record.role, record.page_number).read_bytes()
        assert content == expected_text.encode("utf-8")
        assert record.text_sha256 == hashlib.sha256(content).hexdigest()
        assert record.text_size_bytes == len(content)
        assert record.character_count == len(expected_text)
        assert record.page_sha256 == page.sha256
        assert record.mean_confidence == 0.875


class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, _: Path, __: str) -> OcrResult:
        self.calls += 1
        if self.calls == 2:
            raise OcrProviderError("ocr_fixture_failed", "Synthetic OCR failure.")
        return OcrResult("first page\n", 0.5, "fixture", "1")


def test_ocr_failure_removes_partial_text_but_preserves_page_images(tmp_path: Path) -> None:
    job_id, store, storage = _rendered_job(tmp_path)

    process_ocr_job(
        job_id,
        storage=storage,
        store=store,
        provider=FailingProvider(),
    )

    job = store.get(job_id)
    assert job is not None
    assert job.state is JobState.FAILED
    assert job.stage == "ocr_failed"
    assert job.error_code == "ocr_fixture_failed"
    assert store.list_ocr_pages(job_id) == []
    assert not storage.ocr_path(job_id, "source", 1).exists()
    assert storage.page_path(job_id, "source", 1).exists()
    assert storage.page_path(job_id, "target", 1).exists()


def test_versioned_ocr_config_maps_both_languages() -> None:
    config = TesseractConfig.from_yaml(CONFIG_PATH)

    assert config.provider_language("amh_Ethi") == "amh"
    assert config.provider_language("eng_Latn") == "eng"
    with pytest.raises(OcrProviderError, match="unsupported"):
        config.provider_language("orm_Latn")


def test_ocr_config_rejects_unknown_fields(tmp_path: Path) -> None:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["unreviewed_setting"] = True
    config_path = tmp_path / "ocr.yaml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="missing or unknown"):
        TesseractConfig.from_yaml(config_path)


class EmptyTextProvider:
    def recognize(self, _: Path, __: str) -> OcrResult:
        return OcrResult("", None, "empty-fixture", "1")


def test_empty_ocr_text_remains_an_explicit_checksummed_artifact(tmp_path: Path) -> None:
    job_id, store, storage = _rendered_job(tmp_path)

    run_job_ocr(job_id, storage=storage, store=store, provider=EmptyTextProvider())

    records = store.list_ocr_pages(job_id)
    assert len(records) == 2
    assert all(record.text_size_bytes == 0 for record in records)
    assert all(record.character_count == 0 for record in records)
    assert all(record.mean_confidence is None for record in records)
    assert all(
        storage.ocr_path(job_id, record.role, record.page_number).read_bytes() == b""
        for record in records
    )


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
def test_local_tesseract_smoke_extracts_synthetic_amharic_and_english(
    tmp_path: Path,
) -> None:
    font_specs = [
        ("amh_Ethi", "አንቀጽ ፩", Path("C:/Windows/Fonts/AbyssinicaSIL-Regular.ttf")),
        ("eng_Latn", "Article 123", Path("C:/Windows/Fonts/arial.ttf")),
    ]
    if any(not font_path.is_file() for _, _, font_path in font_specs):
        pytest.skip("Synthetic bilingual smoke fonts are unavailable")
    config = replace(TesseractConfig.from_yaml(CONFIG_PATH), page_segmentation_mode=6)
    provider = TesseractOcrProvider(config)

    for index, (language, text, font_path) in enumerate(font_specs):
        image_path = tmp_path / f"page-{index}.png"
        image = Image.new("RGB", (1000, 220), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), text, fill="black", font=ImageFont.truetype(str(font_path), 80))
        image.save(image_path, format="PNG")

        try:
            result = provider.recognize(image_path, language)
        except OcrProviderError as error:
            if error.code == "ocr_language_data_missing":
                pytest.skip("Required local Tesseract language packs are unavailable")
            raise
        assert result.original_text.strip()
        assert result.engine_name == "tesseract"
        assert result.engine_version.startswith("tesseract ")
        assert result.mean_confidence is None or 0 <= result.mean_confidence <= 1
