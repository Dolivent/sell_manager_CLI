"""Downloader helpers (simplified).

Implements batch daily downloads (concurrent batches of N with pause between).
"""
from typing import Iterable, List, Dict
import time
from .trace import append_trace


def _chunks(seq: List[str], n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def batch_download_daily(ib_client, tickers: Iterable[str], batch_size: int = 32, batch_delay: float = 6.0, duration: str = "1 Y") -> Dict[str, List[dict]]:
    """Download daily data in batches.

    - Splits tickers into batches of `batch_size`.
    - For each batch, issues concurrent download requests (threadpool) for
      daily data (`duration`), waits for all to complete, persists or returns
      results, then sleeps `batch_delay` seconds before starting next batch.

    Returns mapping ticker -> rows (empty list on failure).
    """
    tick_list = list(tickers)
    out: Dict[str, List[dict]] = {}
    if not tick_list:
        return out

    # Process in batches sequentially to avoid ib_insync coroutine warnings from worker threads
    for batch in _chunks(tick_list, batch_size):
        append_trace({"event": "batch_chunk_start", "batch": batch, "batch_size": len(batch)})
        for tk in batch:
            rows = _safe_download_daily(ib_client, tk, duration)
            out[tk] = rows or []
            append_trace({"event": "batch_item_done", "token": tk, "rows": len(rows) if rows else 0})
        # pause between batches
        if batch_delay and batch_delay > 0 and batch is not tick_list[-len(batch) :]:
            time.sleep(batch_delay)
    return out


def _safe_download_daily(ib_client, token: str, duration: str) -> List[dict]:
    try:
        return ib_client.download_daily(token, duration=duration) or []
    except Exception:
        return []


def batch_download_halfhours(ib_client, tickers: Iterable[str], batch_size: int = 32, batch_delay: float = 6.0, duration: str = "31 D", max_bars: int | None = 31) -> Dict[str, List[dict]]:
    """Download half-hour (30m) bars in batches. Returns mapping ticker -> rows (newest last).

    `max_bars` can be used to trim the returned rows to the most recent N bars.
    """
    tick_list = list(tickers)
    out: Dict[str, List[dict]] = {}
    if not tick_list:
        return out

    for batch in _chunks(tick_list, batch_size):
        append_trace({"event": "batch_halfhour_chunk_start", "batch": batch, "batch_size": len(batch)})
        for tk in batch:
            rows = _safe_download_halfhours(ib_client, tk, duration, max_bars)
            out[tk] = rows or []
            append_trace({"event": "batch_halfhour_item_done", "token": tk, "rows": len(rows) if rows else 0})
        if batch_delay and batch_delay > 0 and batch is not tick_list[-len(batch) :]:
            time.sleep(batch_delay)
    return out


def _safe_download_halfhours(ib_client, token: str, duration: str, max_bars: int | None = 31) -> List[dict]:
    try:
        return ib_client.download_halfhours(token, duration=duration, max_bars=max_bars) or []
    except Exception:
        return []
