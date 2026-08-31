"""Validate a local legacy parallel-corpus JSONL file."""

import argparse
from pathlib import Path

from src.rag.legacy_jsonl import validate_legacy_jsonl


def main() -> int:
    """Print sanitized validation counts and return a useful exit code."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Local JSONL file to validate")
    args = parser.parse_args()
    report = validate_legacy_jsonl(args.path)
    print(f"total_rows={report.total_rows}")
    print(f"valid_rows={report.valid_rows}")
    for issue in report.issues:
        print(f"line={issue.line_number} code={issue.code} message={issue.message}")
    return 1 if report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
