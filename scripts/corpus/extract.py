"""CLI entry point for the Negarit Gazeta corpus extractor."""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

# Allow `python scripts/corpus/extract.py` from repository root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.corpus.config import load_config
from src.corpus.ingestion.pdf import find_pdf_files
from src.corpus.ocr.tesseract import validate_environment
from src.corpus.pipeline import extract_pdf_to_json
from src.corpus.export.manifest import write_manifest


def setup_logging(log_dir: Path) -> tuple[logging.Logger, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"extraction_{timestamp}.log"
    logger = logging.getLogger("negarit")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, log_file


def main() -> int:
    config = load_config()
    logger, log_file = setup_logging(config.log_dir)
    print("\n" + "=" * 70)
    print("        NEGARIT GAZETA OCR EXTRACTOR")
    print("=" * 70 + "\n")

    try:
        tesseract, poppler = validate_environment(config)
        logger.info("Tesseract: %s", tesseract)
        logger.info("Poppler: %s", poppler or "system PATH")
        logger.info("OCR DPI: %d", config.ocr_dpi)
    except Exception as exc:
        logger.exception("Environment validation failed")
        print(f"❌ Environment validation failed: {exc}")
        print(f"📋 Log: {log_file}")
        return 1

    pdf_files = find_pdf_files(config)
    if not pdf_files:
        print(f"❌ No PDF files found in: {config.input_dir}")
        return 0

    print(f"📚 Found {len(pdf_files)} PDF file(s)")
    exported: list[Path] = []
    successful = 0
    failed = 0

    for index, pdf_path in enumerate(pdf_files, 1):
        output_file = config.output_dir / f"{pdf_path.stem}.json"
        print("\n" + "=" * 70)
        print(f"📄 FILE {index}/{len(pdf_files)}")
        print(f"📄 {pdf_path.name}")
        print("=" * 70)

        if output_file.exists() and not config.overwrite_output:
            print(f"⏭️ Skipping existing output: {output_file.name}")
            continue

        try:
            extract_pdf_to_json(pdf_path, output_file, config, logger)
            exported.append(output_file)
            successful += 1
        except Exception as exc:
            failed += 1
            logger.exception("Failed to process %s", pdf_path.name)
            print(f"❌ FAILED: {pdf_path.name}: {exc}")

    if config.write_manifest and exported:
        manifest = write_manifest(config.output_dir, exported)
        print(f"🧾 Manifest: {manifest}")

    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"📚 Total PDFs: {len(pdf_files)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📂 Output: {config.output_dir}")
    print(f"📋 Log: {log_file}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n⚠️ Extraction cancelled by user.")
        raise SystemExit(1)
