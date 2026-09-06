"""SHA-256 manifest generation for exported files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(output_dir: Path, exported_files: list[Path]) -> Path:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(exported_files, key=lambda p: p.name.lower())
        ],
    }
    path = output_dir / "manifest.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=4)
    return path
