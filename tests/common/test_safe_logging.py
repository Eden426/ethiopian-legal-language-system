import logging

import pytest

from src.common.safe_logging import PrivacySafeFormatter


def test_formatter_rejects_extracted_text_field() -> None:
    record = logging.LogRecord("ells.jobs", logging.INFO, __file__, 1, "job event", (), None)
    record.extracted_text = "private legal text"
    with pytest.raises(ValueError, match="Unsafe log field"):
        PrivacySafeFormatter("%(message)s").format(record)


def test_formatter_allows_safe_operational_message() -> None:
    record = logging.LogRecord("ells.jobs", logging.INFO, __file__, 1, "job %s entered %s", ("abc", "queued"), None)
    assert PrivacySafeFormatter("%(message)s").format(record) == "job abc entered queued"
