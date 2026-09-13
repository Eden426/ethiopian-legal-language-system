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
    JobState.QUEUED: frozenset({JobState.PROCESSING, JobState.EXPIRED}),
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
    law_type: str
    title: str | None
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


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Small SQLite repository for corpus jobs and uploaded-file metadata."""

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
                    law_type TEXT NOT NULL DEFAULT 'proclamation',
                    title TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )"""
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(corpus_jobs)").fetchall()
            }
            if "law_type" not in columns:
                connection.execute(
                    "ALTER TABLE corpus_jobs ADD COLUMN law_type TEXT NOT NULL "
                    "DEFAULT 'proclamation'"
                )
            if "title" not in columns:
                connection.execute("ALTER TABLE corpus_jobs ADD COLUMN title TEXT")
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
            law_type=law_type,
            title=cleaned_title or None,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO corpus_jobs (
                    id, state, law_type, title, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.id,
                    job.state.value,
                    job.law_type,
                    job.title,
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
                """SELECT id, state, law_type, title, created_at, updated_at, expires_at
                FROM corpus_jobs WHERE id = ?""",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return Job(
            id=row["id"],
            state=JobState(row["state"]),
            law_type=row["law_type"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )

    def transition(self, job_id: str, new_state: JobState) -> Job:
        """Move a job through one allowed lifecycle transition."""

        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        new_state = JobState(new_state)
        if new_state not in VALID_TRANSITIONS[job.state]:
            raise ValueError(f"Invalid job transition: {job.state.value} -> {new_state.value}")
        updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE corpus_jobs SET state = ?, updated_at = ? WHERE id = ?",
                (new_state.value, updated_at, job_id),
            )
        updated = self.get(job_id)
        if updated is None:  # pragma: no cover - protected by the primary key
            raise RuntimeError("Corpus job disappeared during transition")
        return updated

    def record_upload_pair(
        self,
        job_id: str,
        records: Iterable[UploadRecord],
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
                "UPDATE corpus_jobs SET state = ?, updated_at = ? WHERE id = ?",
                (JobState.UPLOADED.value, updated_at, job_id),
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

    def expire_due(self, now: str | None = None) -> int:
        """Expire non-completed jobs whose retention deadline has passed."""

        cutoff = now or utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE corpus_jobs SET state = ?, updated_at = ?
                   WHERE expires_at IS NOT NULL AND expires_at <= ?
                     AND state NOT IN (?, ?)""",
                (
                    JobState.EXPIRED.value,
                    cutoff,
                    cutoff,
                    JobState.COMPLETED.value,
                    JobState.EXPIRED.value,
                ),
            )
            return cursor.rowcount
