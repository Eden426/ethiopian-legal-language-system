"""Canonical, provenance-preserving parallel-corpus data contracts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0-draft"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STABLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,159}$")


class LawType(str, Enum):
    """Legal-source categories supported by the first upload workflow."""

    PROCLAMATION = "proclamation"
    BOOK = "book"


class AlignmentStatus(str, Enum):
    """Human-review state for an aligned bilingual row."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    REJECTED = "rejected"


class SourceType(str, Enum):
    """Permitted origins for source/target text."""

    OFFICIAL = "official"
    HUMAN_TRANSLATED = "human_translated"
    SYNTHETIC_HUMAN_CORRECTED = "synthetic_human_corrected"
    SYNTHETIC_UNVERIFIED = "synthetic_unverified"


class MetadataStatus(str, Enum):
    """Whether document-level metadata is ready for acceptance and splitting."""

    COMPLETE = "complete"
    UNRESOLVED_LEGACY = "unresolved_legacy"


class CorpusModel(BaseModel):
    """Strict base class for versioned corpus records."""

    model_config = ConfigDict(extra="forbid")


class AlignmentScores(CorpusModel):
    """Explainable alignment components; unavailable legacy values remain null."""

    language: float | None = Field(default=None, ge=0.0, le=1.0)
    length_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    numbers_and_dates: float | None = Field(default=None, ge=0.0, le=1.0)
    article_reference: float | None = Field(default=None, ge=0.0, le=1.0)
    text_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=1_000)

    @field_validator("explanation")
    @classmethod
    def require_explanation_text(cls, value: str) -> str:
        """Reject opaque blank explanations without rewriting them."""

        if not value.strip():
            raise ValueError("alignment explanation must not be blank")
        return value

    def all_components_present(self) -> bool:
        """Return whether every required score was actually measured."""

        return all(
            value is not None
            for value in (
                self.language,
                self.length_ratio,
                self.numbers_and_dates,
                self.article_reference,
                self.text_similarity,
            )
        )


class Provenance(CorpusModel):
    """Trace one row to paired files or an explicitly unresolved legacy import."""

    source_file_sha256: str | None = None
    target_file_sha256: str | None = None
    legacy_corpus_sha256: str | None = None
    legacy_line_number: int | None = Field(default=None, ge=1)
    ocr_engine: str | None = Field(default=None, min_length=1, max_length=100)
    ocr_engine_version: str | None = Field(default=None, min_length=1, max_length=100)
    transformations: tuple[str, ...] = ()
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer_id: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator(
        "source_file_sha256",
        "target_file_sha256",
        "legacy_corpus_sha256",
    )
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        """Require lowercase SHA-256 strings without rewriting them."""

        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("checksum must be a 64-character lowercase SHA-256 value")
        return value

    @field_validator("created_at", "reviewed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        """Reject ambiguous timestamps used for dataset provenance."""

        if value is not None and value.utcoffset() is None:
            raise ValueError("provenance timestamps must include a timezone")
        return value

    @field_validator("transformations")
    @classmethod
    def validate_transformations(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep a concise, ordered transformation history."""

        if len(values) > 50:
            raise ValueError("transformation history is limited to 50 entries")
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("transformation entries must contain 1 to 200 characters")
        return values

    @field_validator("ocr_engine", "ocr_engine_version", "reviewer_id")
    @classmethod
    def reject_whitespace_only_metadata(cls, value: str | None) -> str | None:
        """Reject blank provenance labels without rewriting identifiers."""

        if value is not None and not value.strip():
            raise ValueError("provenance labels must not be blank")
        return value

    @model_validator(mode="after")
    def validate_origin(self) -> Provenance:
        """Require a complete paired-file or legacy provenance route."""

        file_values = (self.source_file_sha256, self.target_file_sha256)
        if (file_values[0] is None) != (file_values[1] is None):
            raise ValueError("source and target file checksums must be supplied together")
        legacy_values = (self.legacy_corpus_sha256, self.legacy_line_number)
        if (legacy_values[0] is None) != (legacy_values[1] is None):
            raise ValueError("legacy checksum and line number must be supplied together")
        if file_values[0] is None and legacy_values[0] is None:
            raise ValueError("provenance requires paired-file checksums or a legacy source")
        if (self.ocr_engine is None) != (self.ocr_engine_version is None):
            raise ValueError("OCR engine and version must be supplied together")
        if (self.reviewed_at is None) != (self.reviewer_id is None):
            raise ValueError("reviewed_at and reviewer_id must be supplied together")
        if self.reviewed_at is not None and self.reviewed_at < self.created_at:
            raise ValueError("reviewed_at cannot be earlier than created_at")
        return self


class CanonicalParallelRow(CorpusModel):
    """One versioned Amharic-English alignment with review and provenance."""

    schema_version: str = SCHEMA_VERSION
    id: str
    document_id: str
    legacy_id: int | str | None = None
    law_type: LawType
    title: str | None = Field(default=None, max_length=500)
    chapter_id: str | None = Field(default=None, max_length=120)
    article_id: str | None = Field(default=None, max_length=120)
    paragraph_id: str | None = Field(default=None, max_length=120)
    source_language: str = Field(default="amh_Ethi", pattern=r"^amh_Ethi$")
    target_language: str = Field(default="eng_Latn", pattern=r"^eng_Latn$")
    original_source: str = Field(min_length=1, max_length=100_000)
    original_target: str = Field(min_length=1, max_length=100_000)
    source: str = Field(min_length=1, max_length=100_000)
    target: str = Field(min_length=1, max_length=100_000)
    source_page: int | None = Field(default=None, ge=1)
    target_page: int | None = Field(default=None, ge=1)
    source_type: SourceType
    metadata_status: MetadataStatus = MetadataStatus.COMPLETE
    alignment_status: AlignmentStatus
    alignment_scores: AlignmentScores
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def require_schema_version(cls, value: str) -> str:
        """Reject records written for a different schema revision."""

        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        return value

    @field_validator("id", "document_id")
    @classmethod
    def validate_stable_id(cls, value: str) -> str:
        """Require portable IDs suitable for deterministic filenames and citations."""

        if not STABLE_ID_PATTERN.fullmatch(value):
            raise ValueError("stable IDs must use lowercase ASCII letters, numbers, '.', '_' or '-'")
        return value

    @field_validator("original_source", "original_target", "source", "target")
    @classmethod
    def require_visible_text(cls, value: str) -> str:
        """Reject empty text without trimming or normalizing valid Unicode."""

        if not value.strip():
            raise ValueError("parallel text must not be empty")
        return value

    @field_validator("title", "chapter_id", "article_id", "paragraph_id")
    @classmethod
    def reject_blank_metadata(cls, value: str | None) -> str | None:
        """Use null, not blank strings, for unavailable source metadata."""

        if value is not None and not value.strip():
            raise ValueError("optional metadata must be null or non-empty")
        return value

    @model_validator(mode="after")
    def enforce_review_rules(self) -> CanonicalParallelRow:
        """Prevent unresolved or unreviewed rows from becoming accepted."""

        if (self.source_page is None) != (self.target_page is None):
            raise ValueError("source_page and target_page must be supplied together")
        decided = self.alignment_status in {
            AlignmentStatus.ACCEPTED,
            AlignmentStatus.REJECTED,
        }
        if decided and self.provenance.reviewed_at is None:
            raise ValueError("accepted or rejected rows require reviewer provenance")
        if self.alignment_status is AlignmentStatus.ACCEPTED:
            if self.metadata_status is not MetadataStatus.COMPLETE:
                raise ValueError("unresolved legacy metadata cannot be accepted")
            if self.source_type is SourceType.SYNTHETIC_UNVERIFIED:
                raise ValueError("synthetic_unverified rows cannot be accepted")
            if not self.alignment_scores.all_components_present():
                raise ValueError("accepted rows require every alignment component score")
        text_changed = (
            self.source != self.original_source or self.target != self.original_target
        )
        if text_changed and not self.provenance.transformations:
            raise ValueError("edited or normalized text requires transformation history")
        return self


def make_document_id(law_type: LawType, source_sha256: str, target_sha256: str) -> str:
    """Build a stable document ID from type and immutable paired-file checksums."""

    for checksum in (source_sha256, target_sha256):
        if not SHA256_PATTERN.fullmatch(checksum):
            raise ValueError("document IDs require lowercase SHA-256 checksums")
    material = f"{law_type.value}:{source_sha256}:{target_sha256}"
    suffix = hashlib.sha256(material.encode()).hexdigest()[:20]
    return f"{law_type.value}-{suffix}"


def make_alignment_id(
    document_id: str,
    source_page: int,
    target_page: int,
    sequence: int,
) -> str:
    """Build an edit-stable alignment ID from document/page coordinates."""

    if not STABLE_ID_PATTERN.fullmatch(document_id):
        raise ValueError("document_id is not a valid stable ID")
    if source_page < 1 or target_page < 1 or sequence < 1:
        raise ValueError("page numbers and sequence must be positive")
    alignment_id = f"{document_id}-s{source_page:04d}-t{target_page:04d}-a{sequence:04d}"
    if not STABLE_ID_PATTERN.fullmatch(alignment_id):
        raise ValueError("document_id is too long for a stable alignment ID")
    return alignment_id


def validate_canonical_rows(
    rows: Iterable[CanonicalParallelRow | dict[str, object]],
) -> list[CanonicalParallelRow]:
    """Validate a collection and reject duplicate stable row IDs."""

    validated: list[CanonicalParallelRow] = []
    seen_ids: set[str] = set()
    for value in rows:
        row = (
            value
            if isinstance(value, CanonicalParallelRow)
            else CanonicalParallelRow.model_validate(value)
        )
        if row.id in seen_ids:
            raise ValueError(f"duplicate canonical row id: {row.id}")
        seen_ids.add(row.id)
        validated.append(row)
    return validated
