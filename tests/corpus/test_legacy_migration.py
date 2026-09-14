from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.corpus.legacy import iter_migrated_legacy_rows
from src.corpus.schema import (
    AlignmentStatus,
    LawType,
    MetadataStatus,
    SourceType,
)

FIXTURE_PATH = Path("tests/fixtures/synthetic_legacy_corpus.jsonl")
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_legacy_migration_preserves_text_and_marks_rows_for_review() -> None:
    rows = list(
        iter_migrated_legacy_rows(
            FIXTURE_PATH,
            law_type=LawType.PROCLAMATION,
            source_type=SourceType.SYNTHETIC_UNVERIFIED,
            created_at=CREATED_AT,
        )
    )

    assert len(rows) == 2
    assert rows[0].legacy_id == 1
    assert rows[0].original_source == "ይህ ለስርዓቱ ሙከራ ብቻ የተዘጋጀ ሐረግ ነው።"
    assert rows[0].source == rows[0].original_source
    assert rows[0].target == rows[0].original_target
    assert rows[0].alignment_status is AlignmentStatus.REVIEW
    assert rows[0].metadata_status is MetadataStatus.UNRESOLVED_LEGACY
    assert rows[0].alignment_scores.text_similarity is None
    assert rows[0].provenance.legacy_line_number == 1
    assert rows[0].document_id == rows[1].document_id
    assert rows[0].id != rows[1].id


def test_legacy_migration_is_deterministic_for_fixed_provenance() -> None:
    arguments = {
        "law_type": LawType.PROCLAMATION,
        "source_type": SourceType.SYNTHETIC_UNVERIFIED,
        "created_at": CREATED_AT,
    }

    first = list(iter_migrated_legacy_rows(FIXTURE_PATH, **arguments))
    second = list(iter_migrated_legacy_rows(FIXTURE_PATH, **arguments))

    assert [row.model_dump(mode="json") for row in first] == [
        row.model_dump(mode="json") for row in second
    ]


def test_reviewed_document_id_can_be_supplied_without_accepting_rows() -> None:
    rows = list(
        iter_migrated_legacy_rows(
            FIXTURE_PATH,
            law_type=LawType.BOOK,
            source_type=SourceType.SYNTHETIC_UNVERIFIED,
            created_at=CREATED_AT,
            document_id="book-reviewed-metadata",
            title="Synthetic book fixture",
        )
    )

    assert all(row.document_id == "book-reviewed-metadata" for row in rows)
    assert all(row.metadata_status is MetadataStatus.COMPLETE for row in rows)
    assert all(row.alignment_status is AlignmentStatus.REVIEW for row in rows)


def test_duplicate_legacy_ids_fail_without_exposing_text(tmp_path: Path) -> None:
    corpus = tmp_path / "duplicate.jsonl"
    corpus.write_text(
        '{"id":1,"am":"የግል ያልሆነ ሙከራ","en":"Synthetic one"}\n'
        '{"id":1,"am":"ሌላ ሙከራ","en":"Synthetic two"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as captured:
        list(
            iter_migrated_legacy_rows(
                corpus,
                law_type=LawType.PROCLAMATION,
                source_type=SourceType.SYNTHETIC_UNVERIFIED,
                created_at=CREATED_AT,
            )
        )

    assert "duplicate legacy row id at line 2" == str(captured.value)
    assert "ሌላ" not in str(captured.value)
