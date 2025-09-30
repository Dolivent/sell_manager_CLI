"""Simple adaptive rate limiter inspired by Dolichart's AdaptiveRateLimiter.

Thread-safe and small: exposes get_delay(), on_success(msg), on_failure(msg).
"""
import threading
import logging

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    def __init__(self, initial_delay: float = 0.1, max_delay: float = 30.0):
        self._initial_delay = float(initial_delay)
        self._current_delay = float(initial_delay)
        self._max_delay = float(max_delay)
        self._success_count = 0
        self._failure_count = 0
        self._lock = threading.Lock()

    def get_delay(self) -> float:
        with self._lock:
            return float(self._current_delay)

    def on_success(self) -> None:
        with self._lock:
            self._success_count += 1
            if self._success_count >= 5:
                self._current_delay = max(0.01, self._current_delay * 0.8)
                logger.debug("Rate limiter: reducing delay to %.3fs", self._current_delay)

    def on_failure(self, error_msg: str = "") -> None:
        with self._lock:
            self._failure_count += 1
            em = (error_msg or "").lower()
            if "pacing" in em or "throttl" in em:
                self._current_delay = min(self._max_delay, self._current_delay * 2.0)
                logger.warning("Rate limiter: pacing detected, increasing delay to %.3fs", self._current_delay)
            else:
                self._current_delay = min(self._max_delay, self._current_delay * 1.5)
                logger.debug("Rate limiter: failure, increasing delay to %.3fs", self._current_delay)
            self._failure_count = 0

    def reset(self) -> None:
        with self._lock:
            self._current_delay = float(self._initial_delay)
            self._success_count = 0
            self._failure_count = 0


