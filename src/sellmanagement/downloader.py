"""Downloader helpers (simplified).

Implements batch daily downloads (concurrent batches of N with pause between).
"""
from typing import Iterable, List, Dict
import time
from .trace import append_trace
from .cache import write_bars, merge_bars, load_bars
from .aggregation import aggregate_halfhours_to_hours


def _sequential_backfill_halfhours(ib_client, token: str, batch_durations: List[str] | None = None, target_bars: int = 200) -> List[dict]:
    """Backfill 30-minute bars for a single ticker.

    Repeatedly request 31-bar slices for the ticker. After the first (most
    recent) slice is received, subsequent requests set the `end` parameter to
    the earliest timestamp received so far minus one 30m bar to fetch older
    slices. Continue until `target_bars` is reached or no more rows are
    returned. Requests for a single ticker are executed sequentially to
    avoid pacing problems for that symbol.

    Returns list of bar dicts (newest last).
    """
    # helper to obtain the download function
    rows_fn = getattr(ib_client, "download_halfhours", None) or getattr(ib_client, "download_30m", None)
    if rows_fn is None:
        append_trace({"event": "backfill_no_method", "token": token})
        return []

    out: List[dict] = []
    # `end` is an ISO timestamp string or None
    end: str | None = None
    attempts = 0
    # cap attempts to avoid infinite loops
    max_iterations = max(10, (target_bars // 31) + 2)

    while len(out) < target_bars and attempts < max_iterations:
        attempts += 1
        try:
            append_trace({"event": "backfill_request_start", "token": token, "end": end, "attempt": attempts})
            # rows_fn accepts (token, duration='31 D', end=None)
            res = rows_fn(token, duration="31 D", end=end) or []
            append_trace({"event": "backfill_request_done", "token": token, "count": len(res), "attempt": attempts})
        except Exception as e:
            append_trace({"event": "backfill_request_error", "token": token, "error": str(e), "attempt": attempts})
            break

        if not res:
            # no older data available
            break

        # extend and dedupe by Date later
        out.extend(res)

        # determine earliest Date from combined results to set next `end`
        try:
            # assume Date formatted as ISO-like strings; find minimal
            dates = [r.get("Date") for r in out if r.get("Date")]
            if dates:
                earliest = min(dates)
                # set end to earliest minus 1 minute to avoid overlap (consumer will subtract 30m effectively)
                # For simplicity pass earliest as-is; many IB implementations accept end as string
                end = earliest
        except Exception:
            end = None

        # polite pause between iterative calls
        time.sleep(0.25)

    # dedupe by Date preserving order (oldest first)
    seen = set()
    merged: List[dict] = []
    for r in out:
        d = r.get("Date")
        if d is None:
            s = str(r)
            if s in seen:
                continue
            seen.add(s)
            merged.append(r)
            continue
        if d in seen:
            continue
        seen.add(d)
        merged.append(r)

    # ensure newest-last ordering
    return merged[-target_bars:]


def backfill_halfhours_sequential(ib_client, token: str, target_bars: int = 200) -> List[dict]:
    """Public helper used by tests: backfill until at least `target_bars` 30m bars.

    This wraps `_sequential_backfill_halfhours` with a sensible target of 31
    for quicker unit tests (the test calls with target_bars=31).
    """
    return _sequential_backfill_halfhours(ib_client, token, target_bars=target_bars)


def persist_batch_halfhours(ib_client, tickers: Iterable[str], batch_size: int = 8, batch_delay: float = 6.0, target_bars: int = 200, target_hours: int | None = None) -> Dict[str, int]:
    """For each ticker perform sequential backfill of 30m bars and persist both
    the raw 30m cache and aggregated 1h cache. Returns mapping ticker->bars_persisted.

    The per-ticker backfill is sequential; this helper processes tickers in
    batches to allow controlled parallelism across tickers.
    """
    tick_list = list(tickers)
    out: Dict[str, int] = {}
    if not tick_list:
        return out

    # if caller specified target in hours, convert to half-hour bars
    if target_hours is not None:
        target_bars = int(max(1, target_hours * 2))

    for batch in _chunks(tick_list, batch_size):
        append_trace({"event": "halfhour_batch_start", "batch": batch})
        for tk in batch:
            try:
                # perform sequential 31-bar slices for this ticker and persist after each slice
                rows_fn = getattr(ib_client, "download_halfhours", None) or getattr(ib_client, "download_30m", None)
                if rows_fn is None:
                    append_trace({"event": "backfill_no_method", "token": tk})
                    out[tk] = 0
                    continue

                collected = 0
                end = None
                iterations = 0
                max_iters = max(10, (target_bars // 31) + 2)
                key30 = f"{tk}:30m"
                key1 = f"{tk}:1h"

                while collected < target_bars and iterations < max_iters:
                    iterations += 1
                    try:
                        append_trace({"event": "halfhour_slice_start", "token": tk, "end": end, "iter": iterations})
                        slice_rows = rows_fn(tk, duration="31 D", end=end) or []
                        append_trace({"event": "halfhour_slice_done", "token": tk, "count": len(slice_rows), "iter": iterations})
                    except Exception as e:
                        append_trace({"event": "halfhour_slice_error", "token": tk, "error": str(e), "iter": iterations})
                        break

                    if not slice_rows:
                        break

                    # merge this slice into 30m cache (merge_bars handles replace by Date)
                    try:
                        merge_bars(key30, slice_rows)
                    except Exception:
                        append_trace({"event": "merge_30m_failed", "token": tk, "iter": iterations})

                    # reload full 30m cache and aggregate to hourly, then overwrite 1h cache
                    try:
                        full_halfhours = load_bars(key30)
                        hourly = aggregate_halfhours_to_hours(full_halfhours)
                        write_bars(key1, hourly)
                    except Exception:
                        append_trace({"event": "aggregate_or_write_1h_failed", "token": tk, "iter": iterations})

                    # update counters and set next end based on earliest Date in slice_rows
                    collected = len(load_bars(key30))
                    try:
                        dates = [r.get("Date") for r in slice_rows if r.get("Date")]
                        if dates:
                            # set end to earliest date received (assume ISO) to get older slices next
                            end = min(dates)
                    except Exception:
                        end = None

                    # brief pause between iterative slices
                    time.sleep(0.2)

                out[tk] = collected
            except Exception as e:
                append_trace({"event": "halfhour_batch_item_failed", "token": tk, "error": str(e)})
                out[tk] = 0

        # pause between batches
        if batch_delay and batch_delay > 0 and batch is not tick_list[-len(batch) :]:
            time.sleep(batch_delay)

    return out



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
