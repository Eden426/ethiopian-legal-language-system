from src.corpus.export.dataset_split import (
    split_rows,
    validate_document_isolation,
    validate_id_correspondence,
    write_jsonl,
)


def _rows():
    return [
        {"id": "a-1", "document_id": "doc-a", "source": "alpha law", "target": "alpha law"},
        {"id": "a-2", "document_id": "doc-a", "source": "article one", "target": "article one"},
        {"id": "b-1", "document_id": "doc-b", "source": "beta law", "target": "beta law"},
        {"id": "c-1", "document_id": "doc-c", "source": "gamma law", "target": "gamma law"},
        {"id": "d-1", "document_id": "doc-d", "source": "delta law", "target": "delta law"},
        {"id": "e-1", "document_id": "doc-e", "source": "epsilon law", "target": "epsilon law"},
        {"id": "f-1", "document_id": "doc-f", "source": "zeta law", "target": "zeta law"},
        {"id": "copy-1", "document_id": "doc-copy", "source": "alpha law", "target": "alpha law"},
    ]


def test_split_is_deterministic():
    first = split_rows(_rows(), seed=42, related_similarity_threshold=0.99)
    second = split_rows(_rows(), seed=42, related_similarity_threshold=0.99)
    assert first == second


def test_documents_are_isolated_and_duplicate_content_stays_together():
    splits = split_rows(_rows(), seed=42, related_similarity_threshold=0.99)
    validate_document_isolation(splits)
    locations = {}
    for split, rows in splits.items():
        for row in rows:
            locations[row["document_id"]] = split
    assert locations["doc-a"] == locations["doc-copy"]


def test_ids_correspond_exactly():
    rows = _rows()
    splits = split_rows(rows, seed=7, related_similarity_threshold=0.99)
    validate_id_correspondence(rows, splits)


def test_jsonl_export_is_stable(tmp_path):
    splits = split_rows(_rows(), seed=42, related_similarity_threshold=0.99)
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_jsonl(splits["train"], first)
    write_jsonl(splits["train"], second)
    assert first.read_bytes() == second.read_bytes()


def test_missing_document_id_fails():
    rows = [{"id": "1", "source": "a", "target": "b"}]
    try:
        split_rows(rows)
    except ValueError as exc:
        assert "document_id" in str(exc)
    else:
        raise AssertionError("Expected missing document_id to fail")
