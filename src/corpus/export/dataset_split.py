"""Deterministic document-level train/validation/test splitting.

The splitter keeps every row belonging to a document in one partition and
clusters exact/near-duplicate documents before assignment to prevent leakage.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_RATIOS = {"train": 0.80, "validation": 0.10, "test": 0.10}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).casefold()).strip()


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(
        part for part in (
            row.get("source", ""),
            row.get("target", ""),
            row.get("original_source", ""),
            row.get("original_target", ""),
        ) if part
    )


def _document_signature(rows: list[dict[str, Any]]) -> str:
    text = " ".join(sorted(_normalize(_row_text(row)) for row in rows))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for row in rows:
        for field in ("id", "document_id"):
            if row.get(field) in (None, ""):
                raise ValueError(f"Missing required field: {field}")
        row_id = str(row["id"])
        if row_id in seen_ids:
            raise ValueError(f"Duplicate row id: {row_id}")
        seen_ids.add(row_id)


def _duplicate_groups(doc_rows: dict[str, list[dict[str, Any]]]) -> list[set[str]]:
    """Group documents with identical normalized bilingual content."""
    by_signature: dict[str, set[str]] = defaultdict(set)
    for document_id, rows in doc_rows.items():
        by_signature[_document_signature(rows)].add(document_id)
    return [group for group in by_signature.values()]


def _related_groups(
    doc_rows: dict[str, list[dict[str, Any]]],
    existing_groups: list[set[str]],
    threshold: float,
) -> list[set[str]]:
    """Conservatively cluster documents with high TF-IDF cosine similarity.

    Similarity is computed on whole-document bilingual text. Transitive grouping
    is used so a chain of near-duplicates cannot cross partition boundaries.
    """
    documents = sorted(doc_rows)
    texts = [_document_signature_text(doc_rows[d]) for d in documents]
    if len(documents) < 2:
        return existing_groups

    matrix = TfidfVectorizer(analyzer="word", ngram_range=(1, 3), min_df=1).fit_transform(texts)
    similarities = cosine_similarity(matrix)

    parent = {doc: doc for doc in documents}

    def find(doc: str) -> str:
        while parent[doc] != doc:
            parent[doc] = parent[parent[doc]]
            doc = parent[doc]
        return doc

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, left in enumerate(documents):
        for j in range(i + 1, len(documents)):
            if similarities[i, j] >= threshold:
                union(left, documents[j])

    groups: dict[str, set[str]] = defaultdict(set)
    for doc in documents:
        groups[find(doc)].add(doc)

    # existing_groups is retained as an explicit input so exact duplicate groups
    # are documented by the API; the similarity clustering already subsumes them.
    _ = existing_groups
    return list(groups.values())


def _document_signature_text(rows: list[dict[str, Any]]) -> str:
    return " ".join(sorted(_normalize(_row_text(row)) for row in rows))


def _stable_order(group: set[str], seed: int) -> tuple[str, str]:
    value = "|".join(sorted(group))
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()
    return digest, value


def split_rows(
    rows: Iterable[dict[str, Any]],
    *,
    seed: int = 42,
    related_similarity_threshold: float = 0.92,
    ratios: dict[str, float] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Split rows deterministically into train/validation/test by document.

    Documents are clustered by high bilingual TF-IDF similarity before split
    assignment. Groups are indivisible, so exact 80/10/10 row counts are not
    always mathematically possible; the implementation minimizes deviation from
    the requested targets while preserving document isolation.
    """
    rows = list(rows)
    _validate_rows(rows)
    ratios = ratios or DEFAULT_RATIOS
    if set(ratios) != set(DEFAULT_RATIOS) or not math.isclose(sum(ratios.values()), 1.0):
        raise ValueError("ratios must contain train, validation, test and sum to 1.0")
    if not 0.0 <= related_similarity_threshold <= 1.0:
        raise ValueError("related_similarity_threshold must be between 0 and 1")

    doc_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        doc_rows[str(row["document_id"])].append(row)

    exact_groups = _duplicate_groups(doc_rows)
    groups = _related_groups(doc_rows, exact_groups, related_similarity_threshold)
    groups.sort(key=lambda group: _stable_order(group, seed))

    total_rows = len(rows)
    targets = {name: total_rows * ratio for name, ratio in ratios.items()}
    counts = {name: 0 for name in ratios}
    result: dict[str, list[dict[str, Any]]] = {name: [] for name in ratios}

    # Place larger groups first. Ties use a stable seeded hash.
    groups.sort(key=lambda group: (-sum(len(doc_rows[d]) for d in group), _stable_order(group, seed)))
    for group in groups:
        size = sum(len(doc_rows[d]) for d in group)
        chosen = min(
            counts,
            key=lambda name: (
                max(0, counts[name] + size - targets[name]),
                counts[name] - targets[name],
                name,
            ),
        )
        for document_id in sorted(group):
            result[chosen].extend(doc_rows[document_id])
        counts[chosen] += size

    for split in result:
        result[split].sort(key=lambda row: (str(row["document_id"]), str(row["id"])))

    validate_document_isolation(result)
    return result


def validate_document_isolation(splits: dict[str, list[dict[str, Any]]]) -> None:
    """Raise if a document occurs in more than one exported partition."""
    owners: dict[str, str] = {}
    for split_name, rows in splits.items():
        for row in rows:
            document_id = str(row["document_id"])
            previous = owners.get(document_id)
            if previous is not None and previous != split_name:
                raise ValueError(
                    f"Document leakage detected: {document_id} occurs in {previous} and {split_name}"
                )
            owners[document_id] = split_name


def validate_id_correspondence(source_rows: Iterable[dict[str, Any]], splits: dict[str, list[dict[str, Any]]]) -> None:
    """Verify that every exported row ID occurs exactly once and is source-backed."""
    source_ids = [str(row["id"]) for row in source_rows]
    exported_ids = [str(row["id"]) for rows in splits.values() for row in rows]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Source corpus contains duplicate IDs")
    if set(source_ids) != set(exported_ids) or len(exported_ids) != len(source_ids):
        raise ValueError("Exported IDs do not correspond exactly to source IDs")


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
