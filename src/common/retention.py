"""Retention and cleanup for private corpus job artifacts."""
from __future__ import annotations

import shutil
from datetime import datetime

from src.common.artifact_storage import ArtifactStorageConfig
from src.common.job_store import JobState, JobStore


def cleanup_expired_artifacts(
    config: ArtifactStorageConfig,
    job_store: JobStore,
    now: str | None = None,
) -> list[str]:
    """Delete artifacts for jobs whose authoritative expiry has passed.

    The SQLite ``expires_at`` value is the single source of truth. Filesystem
    modification times are intentionally ignored. Unknown/orphaned artifact
    directories are left untouched for safety.
    """
    cutoff = now or datetime.now().astimezone().isoformat()
    job_store.expire_due(cutoff)

    jobs_root = (config.root / "jobs").resolve()
    jobs_root.mkdir(parents=True, exist_ok=True)
    deleted: list[str] = []

    for job_dir in jobs_root.iterdir():
        if not job_dir.is_dir() or job_dir.is_symlink():
            continue

        job = job_store.get(job_dir.name)
        if job is None or job.state is not JobState.EXPIRED:
            continue

        shutil.rmtree(job_dir)
        deleted.append(job.id)

    return sorted(deleted)
