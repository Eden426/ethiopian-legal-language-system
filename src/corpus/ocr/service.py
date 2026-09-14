"""Page-by-page OCR orchestration with immutable private text artifacts."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from src.common.artifact_storage import ArtifactStorage
from src.common.job_store import Job, JobState, JobStore, OcrRecord, utc_now
from src.corpus.ocr.providers import OcrProvider, OcrProviderError, OcrResult


class OcrPipelineError(RuntimeError):
    """Content-safe validation failure in the OCR orchestration layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _validate_result(result: OcrResult) -> None:
    if not result.engine_name.strip() or not result.engine_version.strip():
        raise OcrPipelineError(
            "ocr_metadata_invalid",
            "The OCR provider omitted required engine metadata.",
        )
    if result.mean_confidence is not None and not 0 <= result.mean_confidence <= 1:
        raise OcrPipelineError(
            "ocr_confidence_invalid",
            "The OCR provider returned confidence outside the supported range.",
        )


def _store_original_text(path: Path, original_text: str) -> bytes:
    content = original_text.encode("utf-8")
    temporary_path = path.with_name(f".{path.stem}-{uuid4().hex}.part")
    try:
        with temporary_path.open("xb") as output:
            output.write(content)
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise OcrPipelineError(
                "ocr_artifact_exists",
                "An OCR artifact already exists for this page.",
            ) from error
    finally:
        temporary_path.unlink(missing_ok=True)
    return content


def run_job_ocr(
    job_id: str,
    *,
    storage: ArtifactStorage,
    store: JobStore,
    provider: OcrProvider,
) -> Job:
    """Extract and atomically record exact original OCR text for every page."""

    job = store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.state is not JobState.PROCESSING or job.stage != "pages_rendered":
        raise OcrPipelineError(
            "job_not_ready_for_ocr",
            "Only a job with complete rendered pages can begin OCR.",
        )
    pages = store.list_pages(job_id)
    if not pages:
        raise OcrPipelineError(
            "rendered_pages_missing",
            "Rendered page metadata is unavailable for OCR.",
        )

    store.update_processing_progress(job_id, 0.0, stage="ocr_processing")
    created_paths: list[Path] = []
    records: list[OcrRecord] = []
    try:
        for completed_pages, page in enumerate(pages, start=1):
            result = provider.recognize(
                storage.page_path(job_id, page.role, page.page_number),
                page.language,
            )
            _validate_result(result)
            destination = storage.ocr_path(job_id, page.role, page.page_number)
            content = _store_original_text(destination, result.original_text)
            created_paths.append(destination)
            records.append(
                OcrRecord(
                    job_id=job_id,
                    role=page.role,
                    language=page.language,
                    page_number=page.page_number,
                    page_sha256=page.sha256,
                    storage_name=destination.name,
                    text_sha256=hashlib.sha256(content).hexdigest(),
                    text_size_bytes=len(content),
                    character_count=len(result.original_text),
                    mean_confidence=result.mean_confidence,
                    engine_name=result.engine_name,
                    engine_version=result.engine_version,
                    created_at=utc_now(),
                )
            )
            store.update_processing_progress(job_id, completed_pages / len(pages))
        return store.record_ocr_pages(job_id, records)
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise


def process_ocr_job(
    job_id: str,
    *,
    storage: ArtifactStorage,
    store: JobStore,
    provider: OcrProvider,
) -> None:
    """Background boundary that records a safe code and preserves page artifacts."""

    job = store.get(job_id)
    if job is None or job.state is not JobState.PROCESSING or job.stage != "pages_rendered":
        return
    try:
        run_job_ocr(job_id, storage=storage, store=store, provider=provider)
    except Exception as error:  # noqa: BLE001 - content-safe background-task boundary
        if isinstance(error, (OcrProviderError, OcrPipelineError)):
            code = error.code
        else:
            code = "ocr_failed"
        current = store.get(job_id)
        if current is not None and current.state is JobState.PROCESSING:
            store.transition(
                job_id,
                JobState.FAILED,
                stage="ocr_failed",
                error_code=code,
            )
