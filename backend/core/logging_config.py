"""
core/logging_config.py — Structured logging setup.

Supports two modes:
  - Plain (default): human-readable for dev
  - JSON (LOG_FORMAT=json): machine-readable for ELK/Loki in production
"""
import logging
import sys
import os
import json
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON — suitable for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            entry.update(record.extra)
        return json.dumps(entry, ensure_ascii=False)


class _PrettyFormatter(logging.Formatter):
    """Human-readable formatter with color hints (works in most terminals)."""

    _COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{self._RESET}"
        ts = datetime.now().strftime("%H:%M:%S")
        return f"{ts} {level} {record.name} | {record.getMessage()}"


def setup_logging(
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """
    Configure root logger. Call once at app startup.

    Args:
        level:       Log level string (DEBUG/INFO/WARNING/ERROR).
                     Falls back to LOG_LEVEL env var, then INFO.
        json_format: If True, emit JSON lines.
                     Falls back to LOG_FORMAT=json env var.
    """
    effective_level = (
        level
        or os.getenv("LOG_LEVEL", "INFO")
    ).upper()
    use_json = json_format if json_format is not None else (
        os.getenv("LOG_FORMAT", "pretty").lower() == "json"
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, effective_level, logging.INFO))

    # Force UTF-8 on Windows to prevent UnicodeEncodeError with ✓ etc.
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JSONFormatter() if use_json else _PrettyFormatter())

    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "httpx", "PIL", "tensorflow", "absl"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
