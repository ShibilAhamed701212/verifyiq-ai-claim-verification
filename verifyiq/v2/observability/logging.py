"""Structured logging for VerifyIQ."""

import json
import logging
import sys
from contextvars import ContextVar

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class StructuredLogAdapter(logging.LoggerAdapter):
    """Wraps a logger and adds structured context to every record."""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        rid = request_id.get()
        if rid:
            extra.setdefault("request_id", rid)
        kwargs["extra"] = extra
        return msg, kwargs


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id") and record.request_id:
            obj["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0]:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configure the root logger for VerifyIQ.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, output JSON-formatted logs (for production).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(root.level)

    if json_format:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a structured logger for the given module name."""
    logger = logging.getLogger(name)
    return StructuredLogAdapter(logger, {})
