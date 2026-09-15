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


def test_retention_cleanup_deletes_only_old_job_directories(tmp_path: Path) -> None:
    root = tmp_path / "private"
    old_job = root / "jobs" / "old-job"
    new_job = root / "jobs" / "new-job"
    old_job.mkdir(parents=True)
    new_job.mkdir(parents=True)
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
    import os
    os.utime(old_job, (old_time, old_time))

    config = ArtifactStorageConfig(root, retention_days=7)
    deleted = cleanup_expired_artifacts(config)
    assert deleted == ["old-job"]
    assert not old_job.exists()
    assert new_job.exists()
