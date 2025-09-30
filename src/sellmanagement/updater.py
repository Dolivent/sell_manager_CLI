"""Minute updater: schedules periodic fetches and triggers indicator recompute.

This is a simple skeleton that runs in a background thread and calls user-provided
fetch functions. Keep this module small and testable.
"""
import threading
import time
from typing import Callable, Optional, List


class MinuteUpdater:
    """Callables:
    - fetch_daily(ticker) -> list[float]
    - fetch_hourly(ticker) -> list[float]
    - on_update(ticker, daily_vals, hourly_vals) -> None
    """

    def __init__(self, fetch_daily: Callable[[str], List[float]], fetch_hourly: Callable[[str], List[float]], on_update: Callable[[str, List[float], List[float]], None], tickers: Optional[List[str]] = None):
        self._fetch_daily = fetch_daily
        self._fetch_hourly = fetch_hourly
        self._on_update = on_update
        self._tickers = list(tickers or [])
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="MinuteUpdater", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                now = time.time()
                # sleep until next minute boundary
                to_sleep = 60 - (int(now) % 60)
                if to_sleep <= 0:
                    to_sleep = 60
                self._stop.wait(to_sleep)
                if self._stop.is_set():
                    break

                # perform per-ticker updates (sequential; downloader handles concurrency)
                for t in list(self._tickers):
                    try:
                        daily = self._fetch_daily(t)
                        hourly = self._fetch_hourly(t)
                        self._on_update(t, daily, hourly)
                    except Exception:
                        # swallow per-ticker errors to avoid stopping the loop
                        continue
            except Exception:
                # top-level safety: avoid crashing the thread
                time.sleep(1)

    def set_tickers(self, tickers: List[str]) -> None:
        self._tickers = list(tickers or [])


