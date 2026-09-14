from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.corpus.schema import (
    AlignmentStatus,
    CanonicalParallelRow,
    LawType,
    make_alignment_id,
    make_document_id,
    validate_canonical_rows,
)


def _accepted_payload() -> dict[str, object]:
    return {
        "id": "proclamation-a1b2-s0003-t0004-a0001",
        "document_id": "proclamation-a1b2",
        "law_type": "proclamation",
        "title": "Synthetic proclamation fixture",
        "chapter_id": None,
        "article_id": "፩",
        "paragraph_id": "1(a)",
        "source_language": "amh_Ethi",
        "target_language": "eng_Latn",
        "original_source": "“አንቀጽ ፩” 1,000.50 ብር አይከፈልም።",
        "original_target": '“Article 1” ETB 1,000.50 shall not be paid.',
        "source": "“አንቀጽ ፩” 1,000.50 ብር አይከፈልም።",
        "target": '“Article 1” ETB 1,000.50 shall not be paid.',
        "source_page": 3,
        "target_page": 4,
        "source_type": "official",
        "metadata_status": "complete",
        "alignment_status": "accepted",
        "alignment_scores": {
            "language": 1.0,
            "length_ratio": 0.91,
            "numbers_and_dates": 1.0,
            "article_reference": 1.0,
            "text_similarity": 0.88,
            "explanation": "Synthetic score fixture; no model result is claimed.",
        },
        "provenance": {
            "source_file_sha256": "a" * 64,
            "target_file_sha256": "b" * 64,
            "ocr_engine": "synthetic-test-provider",
            "ocr_engine_version": "0",
            "transformations": ("unicode_nfc", "whitespace_normalization"),
            "created_at": "2026-01-01T00:00:00+00:00",
            "reviewed_at": "2026-01-02T00:00:00+00:00",
            "reviewer_id": "student-reviewer",
        },
    }


def test_accepted_row_preserves_amharic_punctuation_numbers_and_negation() -> None:
    payload = _accepted_payload()

    row = CanonicalParallelRow.model_validate(payload)

    assert row.original_source == payload["original_source"]
    assert row.source == payload["source"]
    assert "፩" in row.source
    assert "1,000.50" in row.source
    assert "አይከፈልም" in row.source
    assert row.model_dump(mode="json")["alignment_status"] == "accepted"


def test_review_row_allows_unavailable_scores_without_inventing_values() -> None:
    payload = _accepted_payload()
    payload["alignment_status"] = "review"
    payload["metadata_status"] = "unresolved_legacy"
    payload["alignment_scores"] = {
        "explanation": "Scores unavailable until review."
    }
    payload["provenance"] = {
        "legacy_corpus_sha256": "c" * 64,
        "legacy_line_number": 2,
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    row = CanonicalParallelRow.model_validate(payload)

    assert row.alignment_status is AlignmentStatus.REVIEW
    assert row.alignment_scores.language is None


@pytest.mark.parametrize("field", ["original_source", "original_target", "source", "target"])
def test_parallel_text_rejects_empty_values(field: str) -> None:
    payload = _accepted_payload()
    payload[field] = " \n "

    with pytest.raises(ValidationError, match="parallel text must not be empty"):
        CanonicalParallelRow.model_validate(payload)


def test_accepted_row_requires_all_alignment_components() -> None:
    payload = _accepted_payload()
    scores = dict(payload["alignment_scores"])  # type: ignore[arg-type]
    scores["numbers_and_dates"] = None
    payload["alignment_scores"] = scores

    with pytest.raises(ValidationError, match="every alignment component score"):
        CanonicalParallelRow.model_validate(payload)


def test_accepted_row_requires_reviewer_provenance() -> None:
    payload = _accepted_payload()
    provenance = dict(payload["provenance"])  # type: ignore[arg-type]
    provenance["reviewed_at"] = None
    provenance["reviewer_id"] = None
    payload["provenance"] = provenance

    with pytest.raises(ValidationError, match="require reviewer provenance"):
        CanonicalParallelRow.model_validate(payload)


def test_changed_working_text_requires_transformation_history() -> None:
    payload = _accepted_payload()
    payload["source"] = "Normalized synthetic source"
    provenance = dict(payload["provenance"])  # type: ignore[arg-type]
    provenance["transformations"] = ()
    payload["provenance"] = provenance

    with pytest.raises(ValidationError, match="requires transformation history"):
        CanonicalParallelRow.model_validate(payload)


def test_unverified_synthetic_row_cannot_be_accepted() -> None:
    payload = _accepted_payload()
    payload["source_type"] = "synthetic_unverified"

    with pytest.raises(ValidationError, match="cannot be accepted"):
        CanonicalParallelRow.model_validate(payload)


def test_page_references_must_be_paired() -> None:
    payload = _accepted_payload()
    payload["target_page"] = None

    with pytest.raises(ValidationError, match="must be supplied together"):
        CanonicalParallelRow.model_validate(payload)


def test_provenance_requires_lowercase_sha256_and_timezone() -> None:
    payload = _accepted_payload()
    provenance = dict(payload["provenance"])  # type: ignore[arg-type]
    provenance["source_file_sha256"] = "A" * 64
    provenance["created_at"] = "2026-01-01T00:00:00"
    payload["provenance"] = provenance

    with pytest.raises(ValidationError):
        CanonicalParallelRow.model_validate(payload)


def test_stable_id_helpers_are_deterministic_and_text_independent() -> None:
    document_id = make_document_id(LawType.BOOK, "a" * 64, "b" * 64)

    assert document_id == make_document_id(LawType.BOOK, "a" * 64, "b" * 64)
    assert make_alignment_id(document_id, 2, 3, 1) == (
        f"{document_id}-s0002-t0003-a0001"
    )


def test_alignment_id_helper_rejects_document_id_that_makes_an_oversized_id() -> None:
    with pytest.raises(ValueError, match="too long"):
        make_alignment_id("a" * 150, 1, 1, 1)


def test_collection_validation_rejects_duplicate_ids() -> None:
    payload = _accepted_payload()

    with pytest.raises(ValueError, match="duplicate canonical row id"):
        validate_canonical_rows([payload, payload])


def test_schema_rejects_unknown_fields() -> None:
    payload = _accepted_payload()
    payload["opaque_quality_score"] = 0.9

    with pytest.raises(ValidationError):
        CanonicalParallelRow.model_validate(payload)


def test_reviewed_timestamp_is_timezone_aware() -> None:
    payload = _accepted_payload()
    provenance = dict(payload["provenance"])  # type: ignore[arg-type]
    provenance["reviewed_at"] = datetime(2026, 1, 2, tzinfo=timezone.utc)
    payload["provenance"] = provenance

    assert CanonicalParallelRow.model_validate(payload).provenance.reviewed_at is not None
