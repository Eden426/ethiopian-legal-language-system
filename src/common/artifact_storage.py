"""Private local artifact storage with safe path handling."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactStorageConfig:
    """Configuration for private corpus-processing artifacts."""

    root: Path
    retention_days: int = 30

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "ArtifactStorageConfig":
        base = base_dir or Path.cwd()
        raw_root = os.getenv("ELLS_ARTIFACT_ROOT", str(base / "data" / "artifacts"))
        retention = int(os.getenv("ELLS_ARTIFACT_RETENTION_DAYS", "30"))
        if retention < 1:
            raise ValueError("ELLS_ARTIFACT_RETENTION_DAYS must be at least 1")
        root = Path(raw_root).expanduser().resolve()
        return cls(root=root, retention_days=retention)


class ArtifactStorage:
    """Store artifacts under a private root without accepting arbitrary paths."""

    def __init__(self, config: ArtifactStorageConfig) -> None:
        self.config = config
        self.config.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
            raise ValueError("Invalid job_id")
        path = (self.config.root / "jobs" / job_id).resolve()
        jobs_root = (self.config.root / "jobs").resolve()
        if jobs_root not in path.parents:
            raise ValueError("Artifact path escapes storage root")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job_layout(self, job_id: str) -> Path:
        root = self.job_dir(job_id)
        for name in ("uploads", "pages", "ocr", "exports"):
            (root / name).mkdir(exist_ok=True)
        return root
