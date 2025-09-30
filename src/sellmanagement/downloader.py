"""Downloader helpers.

Implements batch daily downloads (concurrent batches of N with pause between)
and sequential half-hour backfill per-ticker until a target number of bars is
retrieved. These are synchronous helpers that call into the provided IB
client (which should provide `download_daily(token, duration)` and
`download_halfhours(token, duration)`).
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Dict, Any
import time
import math
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

    # Use a thread pool sized to batch_size (bounded concurrency per batch)
    for batch in _chunks(tick_list, batch_size):
        append_trace({"event": "batch_chunk_start", "batch": batch, "batch_size": len(batch)})
        with ThreadPoolExecutor(max_workers=min(len(batch), batch_size)) as ex:
            futures = {ex.submit(lambda tk=tk: _safe_download_daily(ib_client, tk, duration), tk): tk for tk in batch}
            for fut in as_completed(futures):
                tk = futures[fut]
                try:
                    rows = fut.result()
                except Exception:
                    rows = []
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


def backfill_halfhours_sequential(ib_client, token: str, target_bars: int = 31, durations: Iterable[str] = None) -> List[dict]:
    """Sequentially backfill 30-minute bars for a ticker until `target_bars` obtained.

    Strategy:
    - Request increasing durations until we collect at least target_bars.
    - Persisting and aggregation handled by caller.
    - Returns list of bars (ordered oldest->newest) up to at least target_bars (may return fewer).
    """
    if durations is None:
        durations = ["2 D", "7 D", "14 D", "31 D", "90 D", "180 D"]
    collected: List[dict] = []
    for d in durations:
        try:
            rows = ib_client.download_halfhours(token, duration=d) or []
        except Exception:
            rows = []
        if not rows:
            continue
        # rows assumed ordered oldest->newest by provider; if not, caller should normalize
        collected = rows
        if len(collected) >= target_bars:
            # return last `target_bars` rows (most recent)
            return collected[-target_bars:]
    # not enough even after longest duration, return whatever we have
    return collected


