"""Streaming validation for the legacy id/am/en JSONL corpus shape."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class LegacyParallelRow(BaseModel):
    """Validated legacy parallel row."""

    model_config = ConfigDict(extra="forbid")

    id: int | str
    am: str
    en: str

    @field_validator("am", "en")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        """Reject empty text without altering valid Unicode."""

        if not value.strip():
            raise ValueError("text must not be empty")
        return value


@dataclass(frozen=True)
class ValidationIssue:
    """Sanitized validation issue without corpus text."""

    line_number: int
    code: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Counts and sanitized issues from one validation pass."""

    total_rows: int
    valid_rows: int
    issues: tuple[ValidationIssue, ...]


def iter_legacy_rows(path: str | Path) -> Iterator[tuple[int, LegacyParallelRow]]:
    """Yield valid non-empty JSONL rows one at a time."""

    corpus_path = Path(path)
    with corpus_path.open(encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            yield line_number, LegacyParallelRow.model_validate(payload)


def validate_legacy_jsonl(path: str | Path) -> ValidationReport:
    """Validate a legacy file without loading its text records into memory."""

    corpus_path = Path(path)
    total_rows = 0
    valid_rows = 0
    issues: list[ValidationIssue] = []
    seen_ids: set[int | str] = set()

    with corpus_path.open(encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            total_rows += 1
            try:
                payload = json.loads(raw_line)
                row = LegacyParallelRow.model_validate(payload)
            except json.JSONDecodeError:
                issues.append(ValidationIssue(line_number, "invalid_json", "Invalid JSON object"))
                continue
            except ValidationError:
                issues.append(
                    ValidationIssue(line_number, "invalid_row", "Required id/am/en fields are invalid")
                )
                continue

            if row.id in seen_ids:
                issues.append(ValidationIssue(line_number, "duplicate_id", "Duplicate row ID"))
                continue
            seen_ids.add(row.id)
            valid_rows += 1

    return ValidationReport(total_rows, valid_rows, tuple(issues))
