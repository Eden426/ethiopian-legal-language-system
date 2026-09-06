"""Legacy JSON exporter: intentionally preserves the existing page-level schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_legacy_json(results: list[dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=4)
