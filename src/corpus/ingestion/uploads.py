"""Bounded, private storage for paired Amharic and English PDF uploads."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO
from uuid import uuid4

from pypdf import PdfReader

from src.common.artifact_storage import ArtifactStorage
from src.common.job_store import Job, JobStore, UploadRecord, utc_now
from src.corpus.schema import LawType, make_document_id

CHUNK_SIZE = 1024 * 1024
PDF_CONTENT_TYPE = "application/pdf"


class PdfUploadError(ValueError):
    """A safe validation error suitable for returning through the API."""

    def __init__(self, code: str, message: str, *, category: str = "invalid") -> None:
        super().__init__(message)
        self.code = code
        self.category = category


@dataclass(frozen=True)
class UploadLimits:
    """Configurable bounds for each uploaded PDF."""

    max_pdf_bytes: int = 50 * 1024 * 1024
    max_pdf_pages: int = 500

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> UploadLimits:
        """Load and validate upload limits without reading document content."""

        source = os.environ if environ is None else environ
        try:
            max_pdf_bytes = int(source.get("ELLS_MAX_PDF_BYTES", str(cls.max_pdf_bytes)))
            max_pdf_pages = int(source.get("ELLS_MAX_PDF_PAGES", str(cls.max_pdf_pages)))
        except ValueError as error:
            raise ValueError("PDF upload limits must be integers") from error
        if max_pdf_bytes < 1:
            raise ValueError("ELLS_MAX_PDF_BYTES must be at least 1")
        if max_pdf_pages < 1:
            raise ValueError("ELLS_MAX_PDF_PAGES must be at least 1")
        return cls(max_pdf_bytes=max_pdf_bytes, max_pdf_pages=max_pdf_pages)


@dataclass(frozen=True)
class PendingPdf:
    """Validated temporary upload awaiting atomic promotion."""

    role: str
    language: str
    original_name: str
    content_type: str
    temporary_path: Path
    destination: Path
    sha256: str
    size_bytes: int
    page_count: int


def _validate_filename(filename: str | None) -> str:
    if not filename:
        raise PdfUploadError("missing_filename", "Each upload must have a filename.")
    if len(filename) > 255 or any(ord(character) < 32 for character in filename):
        raise PdfUploadError("invalid_filename", "An uploaded filename is not safe.")
    if PurePosixPath(filename).name != filename or PureWindowsPath(filename).name != filename:
        raise PdfUploadError("invalid_filename", "An uploaded filename is not safe.")
    if Path(filename).suffix.casefold() != ".pdf":
        raise PdfUploadError(
            "unsupported_file_type",
            "Both uploads must use the .pdf extension.",
            category="media_type",
        )
    return filename


def _validate_content_type(content_type: str | None) -> str:
    if content_type != PDF_CONTENT_TYPE:
        raise PdfUploadError(
            "unsupported_file_type",
            "Both uploads must have the application/pdf content type.",
            category="media_type",
        )
    return content_type


def _read_page_count(path: Path, limits: UploadLimits) -> int:
    try:
        with path.open("rb") as handle:
            reader = PdfReader(handle, strict=False)
            if reader.is_encrypted:
                raise PdfUploadError(
                    "encrypted_pdf",
                    "Password-protected PDFs are not supported.",
                )
            page_count = len(reader.pages)
    except PdfUploadError:
        raise
    except Exception as error:
        raise PdfUploadError("malformed_pdf", "An uploaded PDF could not be read.") from error
    if page_count < 1:
        raise PdfUploadError("empty_pdf", "Each uploaded PDF must contain at least one page.")
    if page_count > limits.max_pdf_pages:
        raise PdfUploadError(
            "too_many_pages",
            f"Each PDF is limited to {limits.max_pdf_pages} pages.",
            category="too_large",
        )
    return page_count


def _stage_pdf(
    *,
    role: str,
    language: str,
    file: BinaryIO,
    filename: str | None,
    content_type: str | None,
    destination: Path,
    limits: UploadLimits,
) -> PendingPdf:
    safe_name = _validate_filename(filename)
    safe_content_type = _validate_content_type(content_type)
    temporary_path = destination.with_name(f".{role}-{uuid4().hex}.part")
    digest = hashlib.sha256()
    size_bytes = 0
    header = bytearray()

    try:
        file.seek(0)
        with temporary_path.open("xb") as output:
            while chunk := file.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > limits.max_pdf_bytes:
                    raise PdfUploadError(
                        "file_too_large",
                        f"Each PDF is limited to {limits.max_pdf_bytes} bytes.",
                        category="too_large",
                    )
                if len(header) < 8:
                    header.extend(chunk[: 8 - len(header)])
                digest.update(chunk)
                output.write(chunk)
        if not bytes(header).startswith(b"%PDF-"):
            raise PdfUploadError(
                "invalid_pdf_signature",
                "An uploaded file does not have a valid PDF signature.",
                category="media_type",
            )
        page_count = _read_page_count(temporary_path, limits)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return PendingPdf(
        role=role,
        language=language,
        original_name=safe_name,
        content_type=safe_content_type,
        temporary_path=temporary_path,
        destination=destination,
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
        page_count=page_count,
    )


def store_upload_pair(
    *,
    job_id: str,
    source_file: BinaryIO,
    source_filename: str | None,
    source_content_type: str | None,
    target_file: BinaryIO,
    target_filename: str | None,
    target_content_type: str | None,
    storage: ArtifactStorage,
    store: JobStore,
    limits: UploadLimits,
) -> tuple[Job, list[UploadRecord]]:
    """Validate and atomically store one Amharic/English PDF pair."""

    job = store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.state.value != "created":
        raise PdfUploadError(
            "job_not_uploadable",
            "Files can only be uploaded to a newly created job.",
            category="conflict",
        )

    source_destination = storage.upload_path(job_id, "source")
    target_destination = storage.upload_path(job_id, "target")
    if source_destination.exists() or target_destination.exists():
        raise PdfUploadError(
            "upload_already_exists",
            "This job already has stored upload files.",
            category="conflict",
        )
    pending: list[PendingPdf] = []
    promoted: list[Path] = []
    try:
        pending.append(
            _stage_pdf(
                role="source",
                language="amh_Ethi",
                file=source_file,
                filename=source_filename,
                content_type=source_content_type,
                destination=source_destination,
                limits=limits,
            )
        )
        pending.append(
            _stage_pdf(
                role="target",
                language="eng_Latn",
                file=target_file,
                filename=target_filename,
                content_type=target_content_type,
                destination=target_destination,
                limits=limits,
            )
        )
        if pending[0].sha256 == pending[1].sha256:
            raise PdfUploadError(
                "identical_language_files",
                "Choose distinct Amharic and English PDFs for the same document.",
            )

        timestamp = utc_now()
        records = [
            UploadRecord(
                job_id=job_id,
                role=item.role,
                language=item.language,
                original_name=item.original_name,
                storage_name=item.destination.name,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                page_count=item.page_count,
                content_type=item.content_type,
                created_at=timestamp,
            )
            for item in pending
        ]
        for item in pending:
            try:
                os.link(item.temporary_path, item.destination)
            except FileExistsError as error:
                raise PdfUploadError(
                    "upload_already_exists",
                    "This job already has stored upload files.",
                    category="conflict",
                ) from error
            item.temporary_path.unlink()
            promoted.append(item.destination)
        try:
            document_id = make_document_id(
                LawType(job.law_type),
                records[0].sha256,
                records[1].sha256,
            )
            updated_job = store.record_upload_pair(
                job_id,
                records,
                document_id=document_id,
            )
        except ValueError as error:
            raise PdfUploadError(
                "job_not_uploadable",
                "Files can only be uploaded to a newly created job.",
                category="conflict",
            ) from error
        return updated_job, records
    except Exception:
        for item in pending:
            item.temporary_path.unlink(missing_ok=True)
        for path in promoted:
            path.unlink(missing_ok=True)
        raise
