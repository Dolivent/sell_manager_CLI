from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_trace_logger: logging.Logger | None = None

# Decimal MB (1 MB = 1_000_000 bytes) to match the historical fixed 10_000_000 cap.
_MIN_MB = 0.1
_MAX_MB = 1024.0
_MAX_BACKUPS = 100
_DEFAULT_MAX_MB = 10.0
_DEFAULT_BACKUPS = 5


def _trace_rotation_settings() -> tuple[int, int]:
    """Return ``(maxBytes, backupCount)`` for :class:`~logging.handlers.RotatingFileHandler`.

    Environment (optional):

    * ``SELLMANAGEMENT_TRACE_MAX_MB`` — float, megabytes as decimal millions of bytes
      (default ``10`` → 10_000_000 bytes).
    * ``SELLMANAGEMENT_TRACE_BACKUPS`` — int, number of rotated files to keep
      (default ``5``; ``0`` keeps only the active file).

    Invalid or empty values fall back to defaults. Values are clamped to safe ranges.
    """
    max_mb = _DEFAULT_MAX_MB
    raw_mb = os.environ.get("SELLMANAGEMENT_TRACE_MAX_MB", "").strip()
    if raw_mb:
        try:
            max_mb = float(raw_mb)
        except ValueError:
            max_mb = _DEFAULT_MAX_MB
    max_mb = max(_MIN_MB, min(max_mb, _MAX_MB))
    max_bytes = int(round(max_mb * 1_000_000))

    backups = _DEFAULT_BACKUPS
    raw_b = os.environ.get("SELLMANAGEMENT_TRACE_BACKUPS", "").strip()
    if raw_b:
        try:
            backups = int(raw_b, 10)
        except ValueError:
            backups = _DEFAULT_BACKUPS
    backups = max(0, min(backups, _MAX_BACKUPS))
    return max_bytes, backups


def _trace_path() -> Path:
    p = Path(__file__).resolve().parents[2] / "logs" / "ibkr_download_trace.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _get_trace_logger() -> logging.Logger:
    global _trace_logger
    if _trace_logger is not None:
        return _trace_logger
    logger = logging.getLogger("sellmanagement.trace")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    max_bytes, backup_count = _trace_rotation_settings()
    fh = logging.handlers.RotatingFileHandler(
        _trace_path(),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.propagate = False
    _trace_logger = logger
    return _trace_logger


def append_trace(record: dict) -> None:
    """Append one JSON object per line (same path and shape as before).

    Rotation size/backups come from ``_trace_rotation_settings()`` (env-tunable; see runbook).
    """
    try:
        ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
        data = {"ts": ts, **record}
        _get_trace_logger().info(json.dumps(data, ensure_ascii=False))
    except Exception:
        logging.getLogger("sellmanagement").warning(
            "append_trace failed", exc_info=True
        )
