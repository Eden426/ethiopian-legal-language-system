from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.common.artifact_storage import ArtifactStorage, ArtifactStorageConfig
from src.common.job_store import JobState, JobStore
from src.common.retention import cleanup_expired_artifacts


def test_artifact_storage_creates_private_job_layout(tmp_path: Path) -> None:
    config = ArtifactStorageConfig(tmp_path / "private", retention_days=7)
    storage = ArtifactStorage(config)
    root = storage.create_job_layout("job-123")
    assert root == (tmp_path / "private" / "jobs" / "job-123").resolve()
    assert all((root / name).is_dir() for name in ("uploads", "pages", "ocr", "exports"))


def test_artifact_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private"))
    with pytest.raises(ValueError):
        storage.job_dir("../escape")


def test_invalid_retention_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ELLS_ARTIFACT_RETENTION_DAYS", "0")
    with pytest.raises(ValueError):
        ArtifactStorageConfig.from_env(tmp_path)


def test_job_state_transitions_and_invalid_transition(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    job = store.create()
    job = store.transition(job.id, JobState.UPLOADED)
    job = store.transition(job.id, JobState.QUEUED)
    job = store.transition(job.id, JobState.PROCESSING)
    assert job.state is JobState.PROCESSING
    with pytest.raises(ValueError):
        store.transition(job.id, JobState.CREATED)


def test_terminal_job_cannot_transition(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    job = store.create()
    for state in (JobState.UPLOADED, JobState.QUEUED, JobState.PROCESSING, JobState.COMPLETED):
        job = store.transition(job.id, state)
    with pytest.raises(ValueError):
        store.transition(job.id, JobState.QUEUED)


def test_expire_due_uses_database_expiration_and_includes_completed_jobs(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.db")
    expired = store.create("2026-01-01T00:00:00+00:00")
    completed = store.create("2026-01-01T00:00:00+00:00")
    completed = store.transition(completed.id, JobState.UPLOADED)
    completed = store.transition(completed.id, JobState.QUEUED)
    completed = store.transition(completed.id, JobState.PROCESSING)
    completed = store.transition(completed.id, JobState.COMPLETED)
    active = store.create("2027-01-01T00:00:00+00:00")

    assert store.expire_due("2026-06-01T00:00:00+00:00") == 2
    assert store.get(expired.id).state is JobState.EXPIRED
    assert store.get(completed.id).state is JobState.EXPIRED
    assert store.get(active.id).state is JobState.CREATED


def test_retention_cleanup_uses_database_expiration_not_filesystem_mtime(tmp_path: Path) -> None:
    root = tmp_path / "private"
    config = ArtifactStorageConfig(root, retention_days=7)
    store = JobStore(tmp_path / "jobs.db")
    expired = store.create("2026-01-01T00:00:00+00:00")
    active = store.create("2027-01-01T00:00:00+00:00")
    storage = ArtifactStorage(config)
    expired_dir = storage.create_job_layout(expired.id)
    active_dir = storage.create_job_layout(active.id)

    old_time = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
    new_time = datetime.now(timezone.utc).timestamp()
    import os
    os.utime(expired_dir, (new_time, new_time))
    os.utime(active_dir, (old_time, old_time))

    deleted = cleanup_expired_artifacts(config, store, "2026-06-01T00:00:00+00:00")

    assert deleted == [expired.id]
    assert not expired_dir.exists()
    assert active_dir.exists()
    assert store.get(expired.id).state is JobState.EXPIRED
    assert store.get(active.id).state is JobState.CREATED


def test_retention_cleanup_leaves_orphan_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "private"
    config = ArtifactStorageConfig(root, retention_days=7)
    store = JobStore(tmp_path / "jobs.db")
    orphan = root / "jobs" / "orphan-job"
    orphan.mkdir(parents=True)

    deleted = cleanup_expired_artifacts(config, store, "2026-06-01T00:00:00+00:00")

    assert deleted == []
    assert orphan.exists()
