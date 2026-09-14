"""Logging helpers that avoid extracted text and local filesystem paths."""
from __future__ import annotations

import logging


class PrivacySafeFormatter(logging.Formatter):
    """Allow structured job metadata while blocking common sensitive fields."""

    BLOCKED_FIELDS = frozenset({"text", "source_text", "target_text", "extracted_text", "path", "local_path"})

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for field in self.BLOCKED_FIELDS:
            if field in record.__dict__:
                raise ValueError(f"Unsafe log field: {field}")
        return message


def get_job_logger(name: str = "ells.jobs") -> logging.Logger:
    """Return a namespaced logger intended for non-content operational events."""
    return logging.getLogger(name)
