from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_trace_logger: logging.Logger | None = None


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
    fh = logging.handlers.RotatingFileHandler(
        _trace_path(),
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.propagate = False
    _trace_logger = logger
    return _trace_logger


def append_trace(record: dict) -> None:
    """Append one JSON object per line (same path and shape as before). Uses rotation."""
    try:
        ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
        data = {"ts": ts, **record}
        _get_trace_logger().info(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass
