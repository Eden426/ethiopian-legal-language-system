"""Retention and cleanup for private corpus job artifacts."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.common.artifact_storage import ArtifactStorageConfig


def cleanup_expired_artifacts(config: ArtifactStorageConfig, now: datetime | None = None) -> list[str]:
    """Delete job artifact directories older than the configured retention period.

    Only directories directly below ``<root>/jobs`` are considered. This keeps
    cleanup scoped to application-owned artifacts and avoids deleting arbitrary
    filesystem paths.
    """
    jobs_root = (config.root / "jobs").resolve()
    jobs_root.mkdir(parents=True, exist_ok=True)
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=config.retention_days)
    deleted: list[str] = []

    for job_dir in jobs_root.iterdir():
        if not job_dir.is_dir() or job_dir.is_symlink():
            continue
        modified = datetime.fromtimestamp(job_dir.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            shutil.rmtree(job_dir)
            deleted.append(job_dir.name)

    return sorted(deleted)
