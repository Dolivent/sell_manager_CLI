"""Download manager with shared concurrency control and adaptive rate limiting.

Provides synchronous download helpers that coordinate concurrent requests
through a semaphore and an AdaptiveRateLimiter to avoid IB pacing violations.
"""
import threading
import time
from typing import Any, List, Optional
import logging

from .rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)


class DownloadManager:
    def __init__(self, ib_client: Any, concurrency: int = 4, initial_delay: float = 0.1, max_delay: float = 30.0):
        self._ib = ib_client
        self._sem = threading.Semaphore(concurrency)
        self._rl = AdaptiveRateLimiter(initial_delay=initial_delay, max_delay=max_delay)

    def download_daily(self, token: str, duration: str = "365 D") -> List[dict]:
        """Blocking download guarded by semaphore and rate limiter."""
        with self._sem:
            delay = self._rl.get_delay()
            if delay and delay > 0:
                try:
                    time.sleep(delay)
                except Exception:
                    pass
            try:
                rows = self._ib.download_daily(token, duration=duration)
                if rows:
                    self._rl.on_success()
                else:
                    # treat empty result as failure to encourage backoff
                    self._rl.on_failure("empty_response")
                return rows or []
            except Exception as e:
                # inform rate limiter
                try:
                    self._rl.on_failure(str(e))
                except Exception:
                    pass
                logger.exception("download_daily failed for %s", token)
                return []

    def download_halfhours(self, token: str, duration: str = "31 D") -> List[dict]:
        with self._sem:
            delay = self._rl.get_delay()
            if delay and delay > 0:
                try:
                    time.sleep(delay)
                except Exception:
                    pass
            try:
                rows = self._ib.download_halfhours(token, duration=duration)
                if rows:
                    self._rl.on_success()
                else:
                    self._rl.on_failure("empty_response")
                return rows or []
            except Exception as e:
                try:
                    self._rl.on_failure(str(e))
                except Exception:
                    pass
                logger.exception("download_halfhours failed for %s", token)
                return []


class DownloadQueue:
    """Background download queue with workers and adaptive rate limiting.

    Enqueue downloads and workers persist results to cache. This prevents the
    updater thread from blocking on network calls.
    """
    def __init__(self, ib_client: Any, workers: int = 2, concurrency: int = 4):
        from queue import Queue

        self._ib = ib_client
        self._queue: "Queue[tuple]" = Queue()
        self._workers: List[threading.Thread] = []
        self._stop = threading.Event()
        self._dm = DownloadManager(ib_client, concurrency=concurrency)
        for i in range(max(1, workers)):
            t = threading.Thread(target=self._worker_loop, name=f"DLWorker-{i}", daemon=True)
            self._workers.append(t)
            t.start()

    def enqueue(self, token: str, kind: str = "daily") -> None:
        self._queue.put((token, kind))

    def _worker_loop(self) -> None:
        from .cache import persist_bars

        while not self._stop.is_set():
            try:
                token, kind = self._queue.get(timeout=1)
            except Exception:
                continue
            try:
                if kind == "daily":
                    rows = self._dm.download_daily(token)
                    if rows:
                        persist_bars(f"{token}:1d", rows)
                else:
                    rows = self._dm.download_halfhours(token)
                    if rows:
                        persist_bars(f"{token}:30m", rows)
            except Exception:
                logger.exception("Download worker failed for %s %s", token, kind)
            finally:
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def stop(self, wait: bool = False) -> None:
        self._stop.set()
        if wait:
            for t in self._workers:
                t.join(timeout=2.0)



