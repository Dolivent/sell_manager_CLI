"""Asynchronous downloader wrapper that runs blocking IB calls in a thread.

This module provides `download_historical_batch` which accepts a sequence
of ticker tokens and downloads daily and half-hour bars using a provided
IB client. It uses a concurrency semaphore to limit parallelism.
"""
import asyncio
from asyncio import Semaphore
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Tuple, List, Any

from .cache import persist_bars


DEFAULT_CONCURRENCY = 8


async def _run_in_thread(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=4) as ex:
        return await loop.run_in_executor(ex, lambda: func(*args, **kwargs))


def _download_for_ib(ib, ticker: str) -> Tuple[str, List[dict], List[dict]]:
    """Blocking download using IB client. Returns (ticker, daily_bars, halfhour_bars).

    This function assumes `ib` exposes `download_symbol_daily` and
    `download_symbol_halfhours` or similar wrappers. If using `ib_insync`, adapt
    callers to pass appropriate wrappers.
    """
    # adaptors: prefer orchestrator-like api if present
    try:
        # daily
        meta_d, daily = ib.download_symbol_daily(ticker)
    except Exception:
        daily = []
    try:
        meta_h, halfhours = ib.download_symbol_halfhours(ticker)
    except Exception:
        halfhours = []
    return ticker, daily, halfhours


async def download_historical_batch(ib, tickers: Iterable[str], concurrency: int = DEFAULT_CONCURRENCY) -> List[Tuple[str, List[dict], List[dict]]]:
    sem = Semaphore(concurrency)
    results: List[Tuple[str, List[dict], List[dict]]] = []

    async def worker(tk: str):
        async with sem:
            # use thread-based executor for blocking IB calls
            r = await _run_in_thread(_download_for_ib, ib, tk)
            # persist to cache quickly (ndjson)
            t, daily, halfs = r
            if daily:
                persist_bars(f"{t}:1d", [dict(b) for b in daily])
            if halfs:
                persist_bars(f"{t}:30m", [dict(b) for b in halfs])
            return r

    tasks = [asyncio.create_task(worker(tk)) for tk in tickers]
    for t in asyncio.as_completed(tasks):
        try:
            r = await t
            results.append(r)
        except Exception:
            # swallow per-symbol failures but continue
            continue
    return results


