"""Bounded rendering of validated PDFs into ordered private page images."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pdf2image import convert_from_path, pdfinfo_from_path

from src.common.artifact_storage import ArtifactStorage
from src.common.job_store import Job, JobState, JobStore, PageRecord, utc_now


class PageRenderError(RuntimeError):
    """Content-safe rendering failure that can be recorded by the worker."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RenderConfig:
    """Validated PDF rendering configuration."""

    dpi: int = 200
    poppler_path: Path | None = None

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> RenderConfig:
        """Load renderer settings without initializing external processes."""

        source = os.environ if environ is None else environ
        try:
            dpi = int(source.get("ELLS_PDF_RENDER_DPI", str(cls.dpi)))
        except ValueError as error:
            raise ValueError("ELLS_PDF_RENDER_DPI must be an integer") from error
        if not 72 <= dpi <= 600:
            raise ValueError("ELLS_PDF_RENDER_DPI must be between 72 and 600")
        raw_path = source.get("ELLS_POPPLER_PATH")
        poppler_path = Path(raw_path).expanduser().resolve() if raw_path else None
        if poppler_path is not None and not poppler_path.is_dir():
            raise ValueError("ELLS_POPPLER_PATH must identify a directory")
        return cls(dpi=dpi, poppler_path=poppler_path)


@dataclass(frozen=True)
class RenderedPage:
    """One rendered PNG returned by a replaceable page renderer."""

    page_number: int
    png_bytes: bytes
    width: int
    height: int


class PageRenderer(Protocol):
    """Replaceable contract for rendering one validated PDF."""

    def render(self, pdf_path: Path, expected_pages: int) -> Iterable[RenderedPage]:
        """Yield PNG pages in one-based document order."""


class Pdf2ImageRenderer:
    """Poppler-backed renderer that holds only one page image at a time."""

    def __init__(self, config: RenderConfig) -> None:
        self.config = config

    def render(self, pdf_path: Path, expected_pages: int) -> Iterator[RenderedPage]:
        """Yield ordered PNG pages while independently verifying page count."""

        poppler_path = str(self.config.poppler_path) if self.config.poppler_path else None
        try:
            info = pdfinfo_from_path(pdf_path, poppler_path=poppler_path)
            actual_pages = int(info["Pages"])
        except Exception as error:
            raise PageRenderError(
                "pdf_renderer_unavailable",
                "The PDF renderer could not inspect this document.",
            ) from error
        if actual_pages != expected_pages:
            raise PageRenderError(
                "page_count_changed",
                "The PDF page count changed after upload validation.",
            )

        for page_number in range(1, actual_pages + 1):
            try:
                images = convert_from_path(
                    pdf_path,
                    dpi=self.config.dpi,
                    first_page=page_number,
                    last_page=page_number,
                    fmt="png",
                    thread_count=1,
                    poppler_path=poppler_path,
                )
                if len(images) != 1:
                    raise PageRenderError(
                        "page_render_failed",
                        "The PDF renderer did not return exactly one page image.",
                    )
                image = images[0]
                try:
                    output = BytesIO()
                    image.save(output, format="PNG")
                    yield RenderedPage(
                        page_number=page_number,
                        png_bytes=output.getvalue(),
                        width=image.width,
                        height=image.height,
                    )
                finally:
                    image.close()
            except PageRenderError:
                raise
            except Exception as error:
                raise PageRenderError(
                    "page_render_failed",
                    "A PDF page could not be rendered.",
                ) from error


def _store_page(path: Path, content: bytes) -> None:
    temporary_path = path.with_name(f".{path.stem}-{uuid4().hex}.part")
    try:
        with temporary_path.open("xb") as output:
            output.write(content)
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise PageRenderError(
                "page_artifact_exists",
                "A rendered page artifact already exists for this job.",
            ) from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _validate_rendered_page(page: RenderedPage, expected_number: int) -> None:
    if page.page_number != expected_number:
        raise PageRenderError(
            "page_order_invalid",
            "The PDF renderer returned pages out of order.",
        )
    if not page.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PageRenderError(
            "page_image_invalid",
            "The PDF renderer returned an invalid page image.",
        )
    if page.width < 1 or page.height < 1:
        raise PageRenderError(
            "page_image_invalid",
            "The PDF renderer returned invalid image dimensions.",
        )


def render_job_pages(
    job_id: str,
    *,
    storage: ArtifactStorage,
    store: JobStore,
    renderer: PageRenderer,
) -> Job:
    """Render and atomically record a complete source/target page set."""

    job = store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.state is not JobState.QUEUED:
        raise PageRenderError(
            "job_not_queued",
            "Only a queued corpus job can begin page rendering.",
        )
    uploads = store.list_uploads(job_id)
    if len(uploads) != 2 or {upload.role for upload in uploads} != {"source", "target"}:
        raise PageRenderError(
            "upload_pair_missing",
            "The validated PDF pair is unavailable for rendering.",
        )

    store.transition(
        job_id,
        JobState.PROCESSING,
        stage="page_rendering",
        progress=0.0,
    )
    total_pages = sum(upload.page_count for upload in uploads)
    completed_pages = 0
    created_paths: list[Path] = []
    records: list[PageRecord] = []
    try:
        for upload in uploads:
            rendered_count = 0
            pages = renderer.render(
                storage.upload_path(job_id, upload.role),
                upload.page_count,
            )
            for expected_number, page in enumerate(pages, start=1):
                if expected_number > upload.page_count:
                    raise PageRenderError(
                        "page_count_changed",
                        "The renderer returned more pages than the validated PDF.",
                    )
                _validate_rendered_page(page, expected_number)
                destination = storage.page_path(job_id, upload.role, expected_number)
                _store_page(destination, page.png_bytes)
                created_paths.append(destination)
                records.append(
                    PageRecord(
                        job_id=job_id,
                        role=upload.role,
                        language=upload.language,
                        page_number=expected_number,
                        storage_name=destination.name,
                        sha256=hashlib.sha256(page.png_bytes).hexdigest(),
                        size_bytes=len(page.png_bytes),
                        width=page.width,
                        height=page.height,
                        created_at=utc_now(),
                    )
                )
                rendered_count += 1
                completed_pages += 1
                store.update_processing_progress(job_id, completed_pages / total_pages)
            if rendered_count != upload.page_count:
                raise PageRenderError(
                    "page_count_changed",
                    "The renderer returned fewer pages than the validated PDF.",
                )
        return store.record_rendered_pages(job_id, records)
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise


def process_render_job(
    job_id: str,
    *,
    storage: ArtifactStorage,
    store: JobStore,
    renderer: PageRenderer,
) -> None:
    """Background-task boundary that records only content-safe failure metadata."""

    try:
        render_job_pages(job_id, storage=storage, store=store, renderer=renderer)
    except Exception as error:  # noqa: BLE001 - content-safe background-task boundary
        code = error.code if isinstance(error, PageRenderError) else "page_render_failed"
        job = store.get(job_id)
        if job is not None and job.state in {JobState.QUEUED, JobState.PROCESSING}:
            store.transition(
                job_id,
                JobState.FAILED,
                stage="page_render_failed",
                error_code=code,
            )
