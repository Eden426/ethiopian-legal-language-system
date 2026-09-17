import logging
from pathlib import Path

import pytest

from src.common.safe_logging import PrivacySafeFormatter, get_job_logger


def test_formatter_rejects_extracted_text_field() -> None:
    record = logging.LogRecord("ells.jobs", logging.INFO, __file__, 1, "job event", (), None)
    record.extracted_text = "private legal text"
    with pytest.raises(ValueError, match="Unsafe log field"):
        PrivacySafeFormatter("%(message)s").format(record)


def test_formatter_rejects_local_path_field() -> None:
    record = logging.LogRecord("ells.jobs", logging.INFO, __file__, 1, "job event", (), None)
    record.local_path = r"C:\private\gazeta.pdf"
    with pytest.raises(ValueError, match="Unsafe log field"):
        PrivacySafeFormatter("%(message)s").format(record)


def test_formatter_allows_safe_operational_message() -> None:
    record = logging.LogRecord("ells.jobs", logging.INFO, __file__, 1, "job %s entered %s", ("abc", "queued"), None)
    assert PrivacySafeFormatter("%(message)s").format(record) == "job abc entered queued"


def test_job_logger_rejects_sensitive_extra_field() -> None:
    logger = get_job_logger()
    with pytest.raises(ValueError, match="Unsafe log field"):
        logger.info("job event", extra={"extracted_text": "private legal text"})


def test_job_logger_rejects_arbitrary_extra_field() -> None:
    logger = get_job_logger()
    with pytest.raises(ValueError, match="Unsafe log field"):
        logger.info("job event", extra={"username": "alice"})


def test_job_logger_rejects_path_argument() -> None:
    logger = get_job_logger()
    with pytest.raises(ValueError, match="Unsafe log argument"):
        logger.info("processing %s", Path(r"C:\private\gazeta.pdf"))


def test_job_logger_rejects_sensitive_message_template() -> None:
    logger = get_job_logger()
    with pytest.raises(ValueError, match="Unsafe log message"):
        logger.info("extracted_text=%s", "private legal text")


def test_job_logger_allows_safe_operational_metadata() -> None:
    logger = get_job_logger()
    logger.info(
        "job event",
        extra={"job_id": "abc", "state": "queued", "page_number": 3},
    )
