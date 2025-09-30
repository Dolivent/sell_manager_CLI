"""Download manager with shared concurrency control and adaptive rate limiting.

Provides synchronous download helpers that coordinate concurrent requests
through a semaphore and an AdaptiveRateLimiter to avoid IB pacing violations.
"""
import threading
import time
from typing import Any, List, Optional
import logging

from .rate_limiter import AdaptiveRateLimiter
from pathlib import Path
import json
from .trace import append_trace

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
        # batch controls (defaults)
        self._batch_size = 32
        self._batch_delay = 6.0
        for i in range(max(1, workers)):
            t = threading.Thread(target=self._worker_loop, name=f"DLWorker-{i}", daemon=True)
            self._workers.append(t)
            t.start()

    def enqueue(self, token: str, kind: str = "daily") -> None:
        append_trace({"event": "enqueue", "token": token, "kind": kind, "queue_size_before": self.queue_size()})
        self._queue.put((token, kind))
        append_trace({"event": "enqueue_done", "token": token, "kind": kind, "queue_size_after": self.queue_size()})

    def queue_size(self) -> int:
        try:
            return self._queue.qsize()
        except Exception:
            return 0

    def rate_limiter_delay(self) -> float:
        try:
            return float(self._dm._rl.get_delay())
        except Exception:
            return 0.0

    def metrics(self) -> dict:
        """Return simple runtime metrics for observability."""
        return {
            "queue_size": self.queue_size(),
            "rate_limiter_delay": self.rate_limiter_delay(),
            "workers": len(self._workers),
        }

    def _failures_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "config" / "download_failures.jsonl"

    def _append_failure(self, token: str, kind: str, err: str) -> None:
        p = self._failures_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with p.open("a", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "token": token, "kind": kind, "error": err}, f)
                f.write("\n")
        except Exception:
            pass

    def retry_failures(self, max_attempts: int = 20) -> dict:
        """Attempt to re-enqueue failures recorded in the failures file.

        Returns summary: {requeued: n, kept: n, cleared: n}
        """
        p = self._failures_path()
        if not p.exists():
            return {"requeued": 0, "kept": 0, "cleared": 0}
        requeued = 0
        kept = 0
        cleared = 0
        lines = []
        try:
            with p.open("r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
        except Exception:
            return {"requeued": 0, "kept": 0, "cleared": 0}

        remaining = []
        for i, line in enumerate(lines):
            if i >= max_attempts:
                remaining.append(line)
                continue
            try:
                obj = json.loads(line)
                tok = obj.get("token")
                kind = obj.get("kind")
                # requeue once
                if tok and kind:
                    try:
                        self.enqueue(tok, kind if kind != 'half' else 'half')
                        requeued += 1
                        cleared += 1
                        continue
                    except Exception:
                        remaining.append(line)
                        kept += 1
                else:
                    # malformed -> drop
                    cleared += 1
            except Exception:
                remaining.append(line)
                kept += 1

        try:
            if remaining:
                with p.open("w", encoding="utf-8") as f:
                    for r in remaining:
                        f.write(r + "\n")
            else:
                p.unlink()
        except Exception:
            pass

        return {"requeued": requeued, "kept": kept, "cleared": cleared}

    def _worker_loop(self) -> None:
        from .cache import persist_bars

        while not self._stop.is_set():
            try:
                token, kind = self._queue.get(timeout=1)
                append_trace({"event": "dequeue", "token": token, "kind": kind, "queue_size": self.queue_size()})
            except Exception:
                continue
            try:
                # Try to form a batch of tokens for efficiency
                batch_size = 32
                tokens = [token]
                if kind in ("daily", "half"):
                    # gather additional items of same kind without blocking
                    try:
                        while len(tokens) < batch_size:
                            tkn, knd = self._queue.get_nowait()
                            if knd == kind:
                                tokens.append(tkn)
                            else:
                                # re-queue mismatched kind
                                self._queue.put((tkn, knd))
                                break
                    except Exception:
                        pass

                if kind == "daily":
                    # batch daily downloads
                    from .downloader import batch_download_daily

                    append_trace({"event": "batch_download_start", "tokens": tokens})
                    results = batch_download_daily(self._ib, tokens, batch_size=batch_size, batch_delay=self._batch_delay, duration="1 Y")
                    append_trace({"event": "batch_download_done", "results_count": len(results)})
                    for tk, rows in results.items():
                        append_trace({"event": "batch_item_result", "token": tk, "rows": len(rows)})
                        if rows:
                            persist_bars(f"{tk}:1d", rows)
                elif kind == "half":
                    # batch half-hour backfills (each ticker backfills sequentially internally)
                    from .downloader import batch_download_daily, backfill_halfhours_sequential
                    # We'll process tokens sequentially but in this batch worker loop to limit bursts
                    append_trace({"event": "half_batch_start", "tokens": tokens})
                    for tk in tokens:
                        try:
                            rows = backfill_halfhours_sequential(self._ib, tk, target_bars=31)
                            if rows:
                                persist_bars(f"{tk}:30m", rows)
                                append_trace({"event": "half_backfill_ok", "token": tk, "rows": len(rows)})
                            else:
                                append_trace({"event": "half_backfill_empty", "token": tk})
                        except Exception as e:
                            logger.exception("failed backfill for %s", tk)
                            append_trace({"event": "half_backfill_error", "token": tk, "error": str(e)})
                else:
                    # fallback single-item processing
                    if kind == 'daily':
                        append_trace({"event": "fallback_single_daily", "token": token})
                        rows = self._dm.download_daily(token)
                        append_trace({"event": "fallback_single_daily_done", "token": token, "rows": len(rows) if rows else 0})
                        if rows:
                            persist_bars(f"{token}:1d", rows)
                    else:
                        append_trace({"event": "fallback_single_half", "token": token})
                        rows = self._dm.download_halfhours(token)
                        append_trace({"event": "fallback_single_half_done", "token": token, "rows": len(rows) if rows else 0})
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



