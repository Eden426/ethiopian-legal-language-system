"""SQLite-backed corpus job records and explicit state transitions."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

LAW_TYPES = frozenset({"proclamation", "book"})
UPLOAD_ROLES = frozenset({"source", "target"})


class JobState(str, Enum):
    """Lifecycle states for a corpus-processing job."""

    CREATED = "created"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


VALID_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.CREATED: frozenset({JobState.UPLOADED, JobState.EXPIRED}),
    JobState.UPLOADED: frozenset({JobState.QUEUED, JobState.EXPIRED}),
    JobState.QUEUED: frozenset({JobState.PROCESSING, JobState.FAILED, JobState.EXPIRED}),
    JobState.PROCESSING: frozenset(
        {JobState.REVIEW, JobState.COMPLETED, JobState.FAILED, JobState.EXPIRED}
    ),
    JobState.REVIEW: frozenset(
        {JobState.PROCESSING, JobState.COMPLETED, JobState.FAILED, JobState.EXPIRED}
    ),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset({JobState.QUEUED, JobState.EXPIRED}),
    JobState.EXPIRED: frozenset(),
}


@dataclass(frozen=True)
class Job:
    """Persisted metadata for one paired-document corpus job."""

    id: str
    state: JobState
    stage: str
    progress: float
    error_code: str | None
    law_type: str
    title: str | None
    document_id: str | None
    created_at: str
    updated_at: str
    expires_at: str | None


@dataclass(frozen=True)
class UploadRecord:
    """Metadata for one privately stored PDF without its extracted text."""

    job_id: str
    role: str
    language: str
    original_name: str
    storage_name: str
    sha256: str
    size_bytes: int
    page_count: int
    content_type: str
    created_at: str


@dataclass(frozen=True)
class PageRecord:
    """Metadata for one rendered page image without its private local path."""

    job_id: str
    role: str
    language: str
    page_number: int
    storage_name: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    created_at: str


@dataclass(frozen=True)
class OcrRecord:
    """Metadata for exact original OCR text stored as a private artifact."""

    job_id: str
    role: str
    language: str
    page_number: int
    page_sha256: str
    storage_name: str
    text_sha256: str
    text_size_bytes: int
    character_count: int
    mean_confidence: float | None
    engine_name: str
    engine_version: str
    created_at: str


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Small SQLite repository for corpus jobs and private artifact metadata."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @classmethod
    def from_database_url(cls, database_url: str) -> JobStore:
        """Create a store from the local MVP's SQLite URL."""

        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Corpus jobs currently require a sqlite:/// database URL")
        return cls(database_url.removeprefix(prefix))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS corpus_jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'awaiting_upload',
                    progress REAL NOT NULL DEFAULT 0,
                    error_code TEXT,
                    law_type TEXT NOT NULL DEFAULT 'proclamation',
                    title TEXT,
                    document_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )"""
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(corpus_jobs)").fetchall()
            }
            migrations = {
                "stage": "TEXT NOT NULL DEFAULT 'awaiting_upload'",
                "progress": "REAL NOT NULL DEFAULT 0",
                "error_code": "TEXT",
                "law_type": "TEXT NOT NULL DEFAULT 'proclamation'",
                "title": "TEXT",
                "document_id": "TEXT",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE corpus_jobs ADD COLUMN {name} {declaration}"
                    )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS corpus_uploads (
                    job_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('source', 'target')),
                    language TEXT NOT NULL CHECK (language IN ('amh_Ethi', 'eng_Latn')),
                    original_name TEXT NOT NULL,
                    storage_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
                    page_count INTEGER NOT NULL CHECK (page_count > 0),
                    content_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, role),
                    FOREIGN KEY (job_id) REFERENCES corpus_jobs(id)
                );

                CREATE INDEX IF NOT EXISTS corpus_uploads_job
                    ON corpus_uploads(job_id, role);

                CREATE TABLE IF NOT EXISTS corpus_pages (
                    job_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('source', 'target')),
                    language TEXT NOT NULL CHECK (language IN ('amh_Ethi', 'eng_Latn')),
                    page_number INTEGER NOT NULL CHECK (page_number > 0),
                    storage_name TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
                    width INTEGER NOT NULL CHECK (width > 0),
                    height INTEGER NOT NULL CHECK (height > 0),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, role, page_number),
                    FOREIGN KEY (job_id, role) REFERENCES corpus_uploads(job_id, role)
                );

                CREATE INDEX IF NOT EXISTS corpus_pages_job
                    ON corpus_pages(job_id, role, page_number);

                CREATE TABLE IF NOT EXISTS corpus_ocr (
                    job_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('source', 'target')),
                    language TEXT NOT NULL CHECK (language IN ('amh_Ethi', 'eng_Latn')),
                    page_number INTEGER NOT NULL CHECK (page_number > 0),
                    page_sha256 TEXT NOT NULL,
                    storage_name TEXT NOT NULL,
                    text_sha256 TEXT NOT NULL,
                    text_size_bytes INTEGER NOT NULL CHECK (text_size_bytes >= 0),
                    character_count INTEGER NOT NULL CHECK (character_count >= 0),
                    mean_confidence REAL CHECK (
                        mean_confidence IS NULL
                        OR (mean_confidence >= 0 AND mean_confidence <= 1)
                    ),
                    engine_name TEXT NOT NULL,
                    engine_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, role, page_number),
                    FOREIGN KEY (job_id, role, page_number)
                        REFERENCES corpus_pages(job_id, role, page_number)
                );

                CREATE INDEX IF NOT EXISTS corpus_ocr_job
                    ON corpus_ocr(job_id, role, page_number);
                """
            )

    def create(
        self,
        expires_at: str | None = None,
        *,
        law_type: str = "proclamation",
        title: str | None = None,
    ) -> Job:
        """Create a job for one proclamation or one bilingual book."""

        if law_type not in LAW_TYPES:
            raise ValueError("law_type must be proclamation or book")
        cleaned_title = title.strip() if title else None
        now = utc_now()
        job = Job(
            id=uuid.uuid4().hex,
            state=JobState.CREATED,
            stage="awaiting_upload",
            progress=0.0,
            error_code=None,
            law_type=law_type,
            title=cleaned_title or None,
            document_id=None,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO corpus_jobs (
                    id, state, stage, progress, error_code, law_type, title, document_id,
                    created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.id,
                    job.state.value,
                    job.stage,
                    job.progress,
                    job.error_code,
                    job.law_type,
                    job.title,
                    job.document_id,
                    job.created_at,
                    job.updated_at,
                    job.expires_at,
                ),
            )
        return job

    def get(self, job_id: str) -> Job | None:
        """Return one job without exposing its private artifact path."""

        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, state, stage, progress, error_code, law_type, title,
                    document_id, created_at, updated_at, expires_at
                FROM corpus_jobs WHERE id = ?""",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return Job(
            id=row["id"],
            state=JobState(row["state"]),
            stage=row["stage"],
            progress=float(row["progress"]),
            error_code=row["error_code"],
            law_type=row["law_type"],
            title=row["title"],
            document_id=row["document_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )

    def transition(
        self,
        job_id: str,
        new_state: JobState,
        *,
        stage: str | None = None,
        progress: float | None = None,
        error_code: str | None = None,
    ) -> Job:
        """Move a job through one allowed lifecycle transition."""

        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        new_state = JobState(new_state)
        if new_state not in VALID_TRANSITIONS[job.state]:
            raise ValueError(f"Invalid job transition: {job.state.value} -> {new_state.value}")
        next_progress = job.progress if progress is None else progress
        if not 0.0 <= next_progress <= 1.0:
            raise ValueError("Job progress must be between 0 and 1")
        next_stage = stage or new_state.value
        updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """UPDATE corpus_jobs
                SET state = ?, stage = ?, progress = ?, error_code = ?, updated_at = ?
                WHERE id = ?""",
                (
                    new_state.value,
                    next_stage,
                    next_progress,
                    error_code,
                    updated_at,
                    job_id,
                ),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the primary key
            raise RuntimeError("Corpus job disappeared during transition")
        return updated

    def update_processing_progress(
        self,
        job_id: str,
        progress: float,
        *,
        stage: str | None = None,
    ) -> Job:
        """Record a bounded stage progress update for a processing job."""

        if not 0.0 <= progress <= 1.0:
            raise ValueError("Job progress must be between 0 and 1")
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        if job.state is not JobState.PROCESSING:
            raise ValueError("Progress can only be updated for a processing job")
        next_stage = stage or job.stage
        if not next_stage.strip():
            raise ValueError("A processing stage is required")
        with self._connect() as connection:
            connection.execute(
                """UPDATE corpus_jobs
                SET stage = ?, progress = ?, error_code = NULL, updated_at = ?
                WHERE id = ?""",
                (next_stage, progress, utc_now(), job_id),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the primary key
            raise RuntimeError("Corpus job disappeared while recording progress")
        return updated

    def record_upload_pair(
        self,
        job_id: str,
        records: Iterable[UploadRecord],
        *,
        document_id: str,
    ) -> Job:
        """Atomically record the two language files and mark the job uploaded."""

        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        if job.state is not JobState.CREATED:
            raise ValueError("Files can only be uploaded to a newly created job")
        pair = list(records)
        if len(pair) != 2 or {record.role for record in pair} != UPLOAD_ROLES:
            raise ValueError("Exactly one source and one target upload are required")
        if any(record.job_id != job_id for record in pair):
            raise ValueError("Upload metadata does not belong to this job")
        if not document_id:
            raise ValueError("A stable document_id is required")

        updated_at = utc_now()
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO corpus_uploads (
                    job_id, role, language, original_name, storage_name, sha256,
                    size_bytes, page_count, content_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        record.job_id,
                        record.role,
                        record.language,
                        record.original_name,
                        record.storage_name,
                        record.sha256,
                        record.size_bytes,
                        record.page_count,
                        record.content_type,
                        record.created_at,
                    )
                    for record in pair
                ],
            )
            connection.execute(
                """UPDATE corpus_jobs
                SET state = ?, stage = ?, progress = 0, error_code = NULL,
                    document_id = ?, updated_at = ?
                WHERE id = ?""",
                (
                    JobState.UPLOADED.value,
                    "upload_validated",
                    document_id,
                    updated_at,
                    job_id,
                ),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the foreign key
            raise RuntimeError("Corpus job disappeared while recording uploads")
        return updated

    def list_uploads(self, job_id: str) -> list[UploadRecord]:
        """Return file metadata in source/target order without local paths."""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT job_id, role, language, original_name, storage_name,
                    sha256, size_bytes, page_count, content_type, created_at
                FROM corpus_uploads
                WHERE job_id = ?
                ORDER BY CASE role WHEN 'source' THEN 0 ELSE 1 END""",
                (job_id,),
            ).fetchall()
        return [UploadRecord(**dict(row)) for row in rows]

    def record_rendered_pages(self, job_id: str, records: Iterable[PageRecord]) -> Job:
        """Atomically record complete ordered page metadata for a processing job."""

        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        if job.state is not JobState.PROCESSING:
            raise ValueError("Pages can only be recorded for a processing job")
        pages = list(records)
        if not pages or any(record.job_id != job_id for record in pages):
            raise ValueError("Rendered page metadata does not belong to this job")
        keys = [(record.role, record.page_number) for record in pages]
        if any(role not in UPLOAD_ROLES or number < 1 for role, number in keys):
            raise ValueError("Rendered page metadata is invalid")
        if len(keys) != len(set(keys)):
            raise ValueError("Rendered page metadata contains duplicate page numbers")
        uploads = self.list_uploads(job_id)
        expected_keys = {
            (upload.role, page_number)
            for upload in uploads
            for page_number in range(1, upload.page_count + 1)
        }
        if set(keys) != expected_keys:
            raise ValueError("Rendered page metadata must match every validated PDF page")
        language_by_role = {upload.role: upload.language for upload in uploads}
        if any(page.language != language_by_role[page.role] for page in pages):
            raise ValueError("Rendered page language does not match its validated upload")

        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO corpus_pages (
                    job_id, role, language, page_number, storage_name, sha256,
                    size_bytes, width, height, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        page.job_id,
                        page.role,
                        page.language,
                        page.page_number,
                        page.storage_name,
                        page.sha256,
                        page.size_bytes,
                        page.width,
                        page.height,
                        page.created_at,
                    )
                    for page in pages
                ],
            )
            connection.execute(
                """UPDATE corpus_jobs
                SET stage = 'pages_rendered', progress = 1, error_code = NULL, updated_at = ?
                WHERE id = ?""",
                (utc_now(), job_id),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the foreign key
            raise RuntimeError("Corpus job disappeared while recording rendered pages")
        return updated

    def list_pages(self, job_id: str) -> list[PageRecord]:
        """Return rendered page metadata in language and page order."""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT job_id, role, language, page_number, storage_name, sha256,
                    size_bytes, width, height, created_at
                FROM corpus_pages
                WHERE job_id = ?
                ORDER BY CASE role WHEN 'source' THEN 0 ELSE 1 END, page_number""",
                (job_id,),
            ).fetchall()
        return [PageRecord(**dict(row)) for row in rows]

    def record_ocr_pages(self, job_id: str, records: Iterable[OcrRecord]) -> Job:
        """Atomically record exact OCR artifact metadata for every rendered page."""

        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        if job.state is not JobState.PROCESSING or job.stage != "ocr_processing":
            raise ValueError("OCR can only be recorded during the OCR processing stage")
        ocr_pages = list(records)
        pages = self.list_pages(job_id)
        page_by_key = {(page.role, page.page_number): page for page in pages}
        keys = [(record.role, record.page_number) for record in ocr_pages]
        if len(keys) != len(set(keys)) or set(keys) != set(page_by_key):
            raise ValueError("OCR metadata must match every rendered page exactly once")
        for record in ocr_pages:
            page = page_by_key[(record.role, record.page_number)]
            if record.job_id != job_id:
                raise ValueError("OCR metadata does not belong to this job")
            if record.language != page.language or record.page_sha256 != page.sha256:
                raise ValueError("OCR provenance does not match its rendered page")
            if record.mean_confidence is not None and not 0 <= record.mean_confidence <= 1:
                raise ValueError("OCR confidence must be between 0 and 1")

        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO corpus_ocr (
                    job_id, role, language, page_number, page_sha256, storage_name,
                    text_sha256, text_size_bytes, character_count, mean_confidence,
                    engine_name, engine_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        record.job_id,
                        record.role,
                        record.language,
                        record.page_number,
                        record.page_sha256,
                        record.storage_name,
                        record.text_sha256,
                        record.text_size_bytes,
                        record.character_count,
                        record.mean_confidence,
                        record.engine_name,
                        record.engine_version,
                        record.created_at,
                    )
                    for record in ocr_pages
                ],
            )
            connection.execute(
                """UPDATE corpus_jobs
                SET stage = 'ocr_complete', progress = 1, error_code = NULL, updated_at = ?
                WHERE id = ?""",
                (utc_now(), job_id),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the foreign key
            raise RuntimeError("Corpus job disappeared while recording OCR artifacts")
        return updated

    def list_ocr_pages(self, job_id: str) -> list[OcrRecord]:
        """Return OCR metadata in language and page order without extracted text."""

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT job_id, role, language, page_number, page_sha256, storage_name,
                    text_sha256, text_size_bytes, character_count, mean_confidence,
                    engine_name, engine_version, created_at
                FROM corpus_ocr
                WHERE job_id = ?
                ORDER BY CASE role WHEN 'source' THEN 0 ELSE 1 END, page_number""",
                (job_id,),
            ).fetchall()
        return [OcrRecord(**dict(row)) for row in rows]

    def expire_due(self, now: str | None = None) -> int:
        """Expire non-completed jobs whose retention deadline has passed."""

        cutoff = now or utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE corpus_jobs SET state = ?, stage = ?, updated_at = ?
                   WHERE expires_at IS NOT NULL AND expires_at <= ?
                     AND state NOT IN (?, ?)""",
                (
                    JobState.EXPIRED.value,
                    JobState.EXPIRED.value,
                    cutoff,
                    cutoff,
                    JobState.COMPLETED.value,
                    JobState.EXPIRED.value,
                ),
            )
            return cursor.rowcount
