"""SQLite-backed corpus job records and explicit state transitions."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path


class JobState(StrEnum):
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
    JobState.PROCESSING: frozenset({JobState.REVIEW, JobState.COMPLETED, JobState.FAILED, JobState.EXPIRED}),
    JobState.REVIEW: frozenset({JobState.PROCESSING, JobState.COMPLETED, JobState.FAILED, JobState.EXPIRED}),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset({JobState.QUEUED, JobState.EXPIRED}),
    JobState.EXPIRED: frozenset(),
}


@dataclass(frozen=True)
class Job:
    id: str
    state: JobState
    created_at: str
    updated_at: str
    expires_at: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Small SQLite repository for corpus processing jobs."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS corpus_jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )"""
            )

    def create(self, expires_at: str | None = None) -> Job:
        now = utc_now()
        job = Job(uuid.uuid4().hex, JobState.CREATED, now, now, expires_at)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO corpus_jobs VALUES (?, ?, ?, ?, ?)",
                (job.id, job.state.value, job.created_at, job.updated_at, job.expires_at),
            )
        return job

    def get(self, job_id: str) -> Job | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM corpus_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return Job(row["id"], JobState(row["state"]), row["created_at"], row["updated_at"], row["expires_at"])

    def transition(self, job_id: str, new_state: JobState) -> Job:
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
        return self.get(job_id)  # type: ignore[return-value]

    def expire_due(self, now: str | None = None) -> int:
        """Expire jobs whose retention deadline has passed."""
        cutoff = now or utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE corpus_jobs SET state = ?, updated_at = ?
                   WHERE expires_at IS NOT NULL AND expires_at <= ?
                     AND state NOT IN (?, ?)""",
                (JobState.EXPIRED.value, cutoff, cutoff, JobState.COMPLETED.value, JobState.EXPIRED.value),
            )
            return cursor.rowcount
