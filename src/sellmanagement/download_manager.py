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
    try:
        from .trace import append_halfhour_trace
        append_halfhour_trace({"event": "batch_halfhour_download_start", "tokens": tokens})
    except Exception:
        pass
    results = batch_download_halfhours(ib_client, tokens, batch_size=batch_size, batch_delay=batch_delay, duration=duration)
    append_trace({"event": "batch_halfhour_download_done", "results_count": len(results)})
    try:
        from .trace import append_halfhour_trace
        append_halfhour_trace({"event": "batch_halfhour_download_done", "results_count": len(results)})
    except Exception:
        pass
    for tk, rows in results.items():
        append_trace({"event": "batch_halfhour_item_result", "token": tk, "rows": len(rows) if rows else 0})
        try:
            from .trace import append_halfhour_trace
            append_halfhour_trace({"event": "batch_halfhour_item_result", "token": tk, "rows": len(rows) if rows else 0})
        except Exception:
            pass
        if rows:
            persist_bars(f"{tk}:30m", rows)


def backfill_halfhours_for_ticker(ib_client: Any, token: str, bars_per_call: int = 31, target_bars: int = 200) -> None:
    """Sequentially download pages of half-hour bars ending earlier and earlier
    until the local half-hour cache for `token` has at least `target_bars` rows.

    This function performs per-ticker serial calls to avoid pacing violations.
    """
    from .downloader import download_halfhours_page
    from .cache import load_bars, persist_bars

    key = f"{token}:30m"
    try:
        from .trace import append_halfhour_trace
        append_halfhour_trace({"event": "backfill_start", "token": token, "target_bars": target_bars})
    except Exception:
        pass
    existing = load_bars(key)
    # if already enough bars, nothing to do
    if len(existing) >= target_bars:
        return

    # determine endDateTime for next page: use oldest existing Date or empty for latest
    pages = 0
    while len(existing) < target_bars:
        end_dt = ''
        if existing:
            oldest = existing[0].get('Date')
            # ask for bars ending before the oldest existing bar
            end_dt = str(oldest)
        rows = download_halfhours_page(ib_client, token, duration=f"{bars_per_call} D", endDateTime=end_dt, max_bars=bars_per_call)
        if not rows:
            # stop on empty response to avoid infinite loop
            break
        persist_bars(key, rows)
        existing = load_bars(key)
        pages += 1
        append_trace({"event": "backfill_page_done", "token": token, "page": pages, "cached": len(existing)})
        try:
            from .trace import append_halfhour_trace
            append_halfhour_trace({"event": "backfill_page_done", "token": token, "page": pages, "cached": len(existing)})
        except Exception:
            pass

    try:
        from .trace import append_halfhour_trace
        append_halfhour_trace({"event": "backfill_done", "token": token, "cached": len(existing)})
    except Exception:
        pass


def backfill_halfhours_for_tokens(ib_client: Any, tokens: List[str], concurrency: int = 4, bars_per_call: int = 31, target_bars: int = 200) -> None:
    """Run per-token backfills in parallel batches (limited concurrency)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        from .trace import append_halfhour_trace
        append_halfhour_trace({"event": "backfill_tokens_start", "tokens": tokens, "concurrency": concurrency})
    except Exception:
        pass

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(backfill_halfhours_for_ticker, ib_client, tk, bars_per_call, target_bars): tk for tk in tokens}
        for fut in as_completed(futures):
            tk = futures[fut]
            try:
                fut.result()
            except Exception as e:
                append_trace({"event": "backfill_failed", "token": tk, "error": str(e)})
                try:
                    from .trace import append_halfhour_trace
                    append_halfhour_trace({"event": "backfill_failed", "token": tk, "error": str(e)})
                except Exception:
                    pass



