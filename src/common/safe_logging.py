"""Logging helpers that avoid extracted text and local filesystem paths."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any


class PrivacySafeFormatter(logging.Formatter):
    """Reject sensitive structured fields before a job log record is rendered."""

    BLOCKED_FIELDS = frozenset(
        {
            "text",
            "source_text",
            "target_text",
            "extracted_text",
            "ocr_text",
            "normalized_text",
            "path",
            "local_path",
            "file_path",
            "source_path",
            "target_path",
            "pdf_path",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        for field in self.BLOCKED_FIELDS:
            if field in record.__dict__:
                raise ValueError(f"Unsafe log field: {field}")
        return super().format(record)


class SafeJobLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that permits only operational job metadata."""

    ALLOWED_EXTRA = frozenset(
        {"job_id", "state", "event", "page_number", "page_count", "row_count", "error_code"}
    )
    BLOCKED_EXTRA = PrivacySafeFormatter.BLOCKED_FIELDS

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        if not self.isEnabledFor(level):
            return
        _validate_log_args(args)
        if _message_mentions_sensitive_content(msg):
            raise ValueError("Unsafe log message")
        super().log(level, msg, *args, **kwargs)

    def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        unsafe = set(extra) & self.BLOCKED_EXTRA
        if unsafe:
            field = sorted(unsafe)[0]
            raise ValueError(f"Unsafe log field: {field}")
        unknown = set(extra) - self.ALLOWED_EXTRA
        if unknown:
            field = sorted(unknown)[0]
            raise ValueError(f"Unsafe log field: {field}")
        return msg, kwargs


def _message_mentions_sensitive_content(message: Any) -> bool:
    if not isinstance(message, str):
        return False
    normalized = message.lower()
    blocked_terms = (
        "extracted_text",
        "ocr_text",
        "source_text",
        "target_text",
        "local_path",
        "file_path",
        "pdf_path",
    )
    return any(term in normalized for term in blocked_terms)


def _validate_log_args(args: Any) -> None:
    values = args.values() if isinstance(args, dict) else args
    for value in values:
        if isinstance(value, Path):
            raise ValueError("Unsafe log argument: filesystem path")
        if isinstance(value, str) and _looks_like_local_path(value):
            raise ValueError("Unsafe log argument: filesystem path")


def _looks_like_local_path(value: str) -> bool:
    expanded = os.path.expanduser(value)
    return (
        os.path.isabs(expanded)
        or expanded.startswith("\\\\")
        or (len(expanded) >= 3 and expanded[1:3] == ":\\")
        or (len(expanded) >= 3 and expanded[1:3] == ":/")
    )


def get_job_logger(name: str = "ells.jobs") -> SafeJobLoggerAdapter:
    """Return a logger restricted to non-content operational events."""
    logger = logging.getLogger(name)
    return SafeJobLoggerAdapter(logger, {})
