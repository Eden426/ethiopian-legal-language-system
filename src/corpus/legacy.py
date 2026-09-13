"""Traceable migration from the legacy ``id``/``am``/``en`` JSONL shape."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from src.corpus.schema import (
    SHA256_PATTERN,
    AlignmentScores,
    AlignmentStatus,
    CanonicalParallelRow,
    LawType,
    MetadataStatus,
    Provenance,
    SourceType,
)
from src.rag.legacy_jsonl import LegacyParallelRow, iter_legacy_rows


def sha256_file(path: str | Path) -> str:
    """Hash a legacy corpus without loading it or exposing its text."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_legacy_alignment_id(corpus_sha256: str, legacy_id: int | str) -> str:
    """Build a stable row ID while preserving the original ID separately."""

    if not SHA256_PATTERN.fullmatch(corpus_sha256):
        raise ValueError("legacy IDs require a lowercase SHA-256 corpus checksum")
    material = json.dumps(
        [type(legacy_id).__name__, legacy_id],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    suffix = hashlib.sha256(material.encode()).hexdigest()[:16]
    return f"legacy-{corpus_sha256[:20]}-{suffix}"


def migrate_legacy_row(
    row: LegacyParallelRow,
    *,
    corpus_sha256: str,
    line_number: int,
    law_type: LawType,
    source_type: SourceType,
    created_at: datetime,
    document_id: str | None = None,
    title: str | None = None,
) -> CanonicalParallelRow:
    """Map one legacy row without inventing scores, pages, or document metadata."""

    resolved_document_id = document_id or f"legacy-unresolved-{corpus_sha256[:20]}"
    metadata_status = (
        MetadataStatus.COMPLETE if document_id else MetadataStatus.UNRESOLVED_LEGACY
    )
    return CanonicalParallelRow(
        id=make_legacy_alignment_id(corpus_sha256, row.id),
        document_id=resolved_document_id,
        legacy_id=row.id,
        law_type=law_type,
        title=title,
        source_language="amh_Ethi",
        target_language="eng_Latn",
        original_source=row.am,
        original_target=row.en,
        source=row.am,
        target=row.en,
        source_page=None,
        target_page=None,
        source_type=source_type,
        metadata_status=metadata_status,
        alignment_status=AlignmentStatus.REVIEW,
        alignment_scores=AlignmentScores(
            explanation="Legacy import; alignment component scores are unavailable.",
        ),
        provenance=Provenance(
            legacy_corpus_sha256=corpus_sha256,
            legacy_line_number=line_number,
            transformations=("legacy_id_am_en_mapping",),
            created_at=created_at,
        ),
    )


def iter_migrated_legacy_rows(
    path: str | Path,
    *,
    law_type: LawType,
    source_type: SourceType,
    created_at: datetime,
    document_id: str | None = None,
    title: str | None = None,
) -> Iterator[CanonicalParallelRow]:
    """Stream canonical review rows from a validated legacy JSONL file."""

    corpus_sha256 = sha256_file(path)
    seen_ids: set[int | str] = set()
    for line_number, row in iter_legacy_rows(path):
        if row.id in seen_ids:
            raise ValueError(f"duplicate legacy row id at line {line_number}")
        seen_ids.add(row.id)
        yield migrate_legacy_row(
            row,
            corpus_sha256=corpus_sha256,
            line_number=line_number,
            law_type=law_type,
            source_type=source_type,
            created_at=created_at,
            document_id=document_id,
            title=title,
        )
