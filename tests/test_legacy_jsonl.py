from pathlib import Path

from src.rag.legacy_jsonl import iter_legacy_rows, validate_legacy_jsonl

FIXTURE_PATH = Path("tests/fixtures/synthetic_legacy_corpus.jsonl")


def test_streams_synthetic_amharic_english_rows() -> None:
    rows = list(iter_legacy_rows(FIXTURE_PATH))

    assert [row.id for _, row in rows] == [1, 2]
    assert rows[0][1].am == "ይህ ለስርዓቱ ሙከራ ብቻ የተዘጋጀ ሐረግ ነው።"


def test_reports_malformed_empty_and_duplicate_rows_without_text(tmp_path: Path) -> None:
    corpus_path = tmp_path / "invalid.jsonl"
    corpus_path.write_text(
        """{"id": 1, "am": "ሙከራ", "en": "Test"}
{"id": 1, "am": "ሌላ", "en": "Another"}
{"id": 2, "am": "", "en": "Empty source"}
not-json""",
        encoding="utf-8",
    )

    report = validate_legacy_jsonl(corpus_path)

    assert report.total_rows == 4
    assert report.valid_rows == 1
    assert [issue.code for issue in report.issues] == [
        "duplicate_id",
        "invalid_row",
        "invalid_json",
    ]
    assert all("ሌላ" not in issue.message for issue in report.issues)
