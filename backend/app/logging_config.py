# app/logging_config.py

import json
import logging
import sys
from datetime import datetime, timezone

# Standard LogRecord attributes to skip when merging extra= kwargs into JSON output.
_STDLIB_ATTRS = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line on stdout."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra= kwargs, skipping standard LogRecord internals.
        for key, value in record.__dict__.items():
            if key not in _STDLIB_ATTRS and not key.startswith("_"):
                log_obj[key] = value
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        # default=str handles datetime, ObjectId, and other non-serialisable types.
        return json.dumps(log_obj, default=str)


def setup_logging(log_level: str) -> None:
    """
    Configure the root logger with JSON output on stdout.

    Called once at application startup (module level in main.py) before any
    router imports so that all modules inherit the configured handlers.
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    # Quiet noisy third-party loggers that would otherwise flood the output.
    for noisy in ("motor", "pymongo", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
