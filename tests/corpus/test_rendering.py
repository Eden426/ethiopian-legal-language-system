from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from src.common.artifact_storage import ArtifactStorage, ArtifactStorageConfig
from src.common.job_store import JobState, JobStore
from src.corpus.ingestion.rendering import (
    Pdf2ImageRenderer,
    RenderConfig,
    RenderedPage,
    process_render_job,
    render_job_pages,
)
from src.corpus.ingestion.uploads import UploadLimits, store_upload_pair


def _pdf_bytes(widths: list[int]) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=300)
    writer.write(output)
    return output.getvalue()


def _queued_job(tmp_path: Path) -> tuple[str, JobStore, ArtifactStorage]:
    store = JobStore(tmp_path / "ells.db")
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private"))
    job = store.create(law_type="proclamation", title="Synthetic rendering fixture")
    store_upload_pair(
        job_id=job.id,
        source_file=BytesIO(_pdf_bytes([100, 110])),
        source_filename="source.pdf",
        source_content_type="application/pdf",
        target_file=BytesIO(_pdf_bytes([120])),
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
    return job.id, store, storage


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler is not installed")
def test_synthetic_pdf_rendering_preserves_page_order_count_and_checksums(
    tmp_path: Path,
) -> None:
    job_id, store, storage = _queued_job(tmp_path)

    job = render_job_pages(
        job_id,
        storage=storage,
        store=store,
        renderer=Pdf2ImageRenderer(RenderConfig(dpi=72)),
    )

    pages = store.list_pages(job_id)
    assert job.state is JobState.PROCESSING
    assert job.stage == "pages_rendered"
    assert job.progress == 1.0
    assert [(page.role, page.page_number) for page in pages] == [
        ("source", 1),
        ("source", 2),
        ("target", 1),
    ]
    assert [(page.width, page.height) for page in pages] == [
        (100, 300),
        (110, 300),
        (120, 300),
    ]
    for page in pages:
        content = storage.page_path(job_id, page.role, page.page_number).read_bytes()
        assert content.startswith(b"\x89PNG\r\n\x1a\n")
        assert page.sha256 == hashlib.sha256(content).hexdigest()
        assert page.size_bytes == len(content)


class OutOfOrderRenderer:
    def render(self, _: Path, __: int) -> Iterable[RenderedPage]:
        yield RenderedPage(1, b"\x89PNG\r\n\x1a\nfirst", 10, 20)
        yield RenderedPage(3, b"\x89PNG\r\n\x1a\nthird", 10, 20)


def test_rendering_failure_removes_partial_pages_and_records_safe_code(
    tmp_path: Path,
) -> None:
    job_id, store, storage = _queued_job(tmp_path)

    process_render_job(
        job_id,
        storage=storage,
        store=store,
        renderer=OutOfOrderRenderer(),
    )

    job = store.get(job_id)
    assert job is not None
    assert job.state is JobState.FAILED
    assert job.stage == "page_render_failed"
    assert job.error_code == "page_order_invalid"
    assert store.list_pages(job_id) == []
    assert not storage.page_path(job_id, "source", 1).exists()


@pytest.mark.parametrize("dpi", ["71", "601", "not-a-number"])
def test_render_config_rejects_unsafe_dpi(dpi: str) -> None:
    with pytest.raises(ValueError):
        RenderConfig.from_env({"ELLS_PDF_RENDER_DPI": dpi})
