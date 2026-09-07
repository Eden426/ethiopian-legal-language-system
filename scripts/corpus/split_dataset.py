"""Export a deterministic 80/10/10 document-isolated corpus split."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.corpus.export.dataset_split import split_rows, validate_id_correspondence, write_jsonl
from src.corpus.export.manifest import sha256_file


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic document-isolated dataset splits")
    parser.add_argument("input", type=Path, help="Canonical corpus JSONL")
    parser.add_argument("output_dir", type=Path, help="Directory for train/validation/test JSONL")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--related-threshold", type=float, default=0.92)
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    splits = split_rows(rows, seed=args.seed, related_similarity_threshold=args.related_threshold)
    validate_id_correspondence(rows, splits)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, split_rows_value in splits.items():
        path = args.output_dir / f"{name}.jsonl"
        write_jsonl(split_rows_value, path)
        files[name] = path

    manifest = {
        "schema": "canonical-parallel-corpus",
        "split_ratios": {"train": 0.8, "validation": 0.1, "test": 0.1},
        "seed": args.seed,
        "related_similarity_threshold": args.related_threshold,
        "source_file": str(args.input),
        "source_sha256": sha256_file(args.input),
        "splits": {
            name: {
                "file": path.name,
                "sha256": sha256_file(path),
                "rows": len(splits[name]),
                "documents": len({str(row["document_id"]) for row in splits[name]}),
            }
            for name, path in files.items()
        },
    }
    manifest_path = args.output_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote dataset splits to {args.output_dir}")
    for name in ("train", "validation", "test"):
        print(f"{name}: {len(splits[name])} rows, {len({str(r['document_id']) for r in splits[name]})} documents")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
