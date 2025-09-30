"""Simplified download manager wrapper retained only for daily persistence helpers."""
from typing import Any, List
from .trace import append_trace


def persist_batch_daily(ib_client: Any, tokens: List[str], batch_size: int = 32, batch_delay: float = 6.0, duration: str = "1 Y") -> None:
    """Download and persist daily bars for tokens in batches."""
    from .downloader import batch_download_daily
    from .cache import persist_bars

    append_trace({"event": "batch_download_start", "tokens": tokens})
    results = batch_download_daily(ib_client, tokens, batch_size=batch_size, batch_delay=batch_delay, duration=duration)
    append_trace({"event": "batch_download_done", "results_count": len(results)})
    for tk, rows in results.items():
        append_trace({"event": "batch_item_result", "token": tk, "rows": len(rows)})
        if rows:
            persist_bars(f"{tk}:1d", rows)


def persist_halfhour_once(ib_client: Any, tokens: List[str], batch_size: int = 32, batch_delay: float = 6.0, duration: str = "31 D") -> None:
    """Download a single half-hour (30m) chunk for each token and persist into cache.

    This function performs batch downloads of the most recent `duration` half-hour
    bars (default '31 D' / '31 bars' per token according to IB settings) and writes
    them into the half-hour cache key `token:30m`.
    """
    from .downloader import batch_download_halfhours
    from .cache import persist_bars

    append_trace({"event": "batch_halfhour_download_start", "tokens": tokens})
    results = batch_download_halfhours(ib_client, tokens, batch_size=batch_size, batch_delay=batch_delay, duration=duration)
    append_trace({"event": "batch_halfhour_download_done", "results_count": len(results)})
    for tk, rows in results.items():
        append_trace({"event": "batch_halfhour_item_result", "token": tk, "rows": len(rows) if rows else 0})
        if rows:
            persist_bars(f"{tk}:30m", rows)



