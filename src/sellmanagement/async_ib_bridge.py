"""Async IB bridge: runs an asyncio event loop in a dedicated thread and owns an IB() instance.

This allows worker threads to schedule async IB coroutines via
`asyncio.run_coroutine_threadsafe(...)` safely and avoid "no event loop in thread" errors.
"""
import asyncio
import threading
import time
from typing import Optional
from collections import deque
from .trace import append_trace

try:
    from ib_insync import IB
except Exception:
    IB = None  # allow tests/machines without ib_insync


class AsyncIBBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1, rate_limit: int = 50):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.ib: Optional[IB] = None
        self._started = threading.Event()
        self._stopping = threading.Event()
        # simple thread-safe sliding-window rate limiter (requests per second)
        self._rate_limit = int(rate_limit or 50)
        self._req_times = deque()
        self._req_lock = threading.Lock()
        # connection status
        self.status = "starting"

    def start(self, wait_timeout: float = 10.0) -> None:
        if self.thread and self.thread.is_alive():
            return

        def _run_loop():
            # create and set loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            # create IB instance in this thread
            try:
                if IB is None:
                    self.ib = None
                else:
                    self.ib = IB()
                # mark started even if not connected yet; maintainer will try connect
                self._started.set()

                async def _maintain_connection():
                    backoff = 1.0
                    while not self._stopping.is_set():
                        try:
                            if IB is None:
                                self.status = "no_ib"
                                await asyncio.sleep(1.0)
                                continue

                            if self.ib is None:
                                self.ib = IB()

                            connected = False
                            try:
                                connected = getattr(self.ib, 'isConnected', lambda: False)()
                            except Exception:
                                connected = False

                            if not connected:
                                # attempt blocking connect on executor to avoid blocking loop
                                try:
                                    await self.loop.run_in_executor(None, lambda: self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=10))
                                    self.status = "connected"
                                    try:
                                        append_trace({"event": "bridge_connected", "host": self.host, "port": self.port})
                                    except Exception:
                                        pass
                                    backoff = 1.0
                                except Exception as e:
                                    self.status = "connect_failed"
                                    try:
                                        append_trace({"event": "bridge_connect_failed", "error": str(e), "backoff": backoff})
                                    except Exception:
                                        pass
                                    await asyncio.sleep(backoff)
                                    backoff = min(backoff * 2.0, 60.0)
                                    continue
                            else:
                                # connected: sleep a bit
                                await asyncio.sleep(1.0)
                        except Exception as e:
                            try:
                                append_trace({"event": "bridge_maintain_error", "error": str(e)})
                            except Exception:
                                pass
                            await asyncio.sleep(1.0)

                # schedule maintainer task
                try:
                    self.loop.create_task(_maintain_connection())
                except Exception:
                    # fallback: run maintain in executor
                    pass

                try:
                    self.loop.run_forever()
                finally:
                    # cleanup on exit
                    try:
                        self._stopping.set()
                        if self.ib is not None and getattr(self.ib, 'isConnected', lambda: False)():
                            try:
                                self.ib.disconnect()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        # close loop
                        self.loop.close()
                    except Exception:
                        pass

        self.thread = threading.Thread(target=_run_loop, name="AsyncIBBridge", daemon=True)
        self.thread.start()
        self._started.wait(wait_timeout)

    def _acquire_slot(self) -> None:
        """Block until a request slot is available under rate limit."""
        while True:
            with self._req_lock:
                now = time.monotonic()
                # drop timestamps older than 1s
                while self._req_times and now - self._req_times[0] >= 1.0:
                    self._req_times.popleft()
                if len(self._req_times) < self._rate_limit:
                    self._req_times.append(now)
                    return
                # otherwise compute sleep until earliest expires
                earliest = self._req_times[0]
                wait = max(0.01, 1.0 - (now - earliest))
            time.sleep(wait)

    def stop(self) -> None:
        if not self.loop:
            return
        try:
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        if self.thread:
            self.thread.join(timeout=5.0)

    def run_coroutine(self, coro):
        """Schedule coroutine `coro` on the bridge loop and return a concurrent.futures.Future.

        Caller can call `future.result(timeout=...)` to wait.
        """
        if not self.loop:
            raise RuntimeError("AsyncIBBridge not started")
        # throttle scheduling to respect IB pacing
        try:
            self._acquire_slot()
            append_trace({"event": "bridge_schedule", "info": "scheduling_coroutine"})
        except Exception:
            pass
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def run_coroutine_and_wait(self, coro, timeout: float = 15.0):
        """Convenience: schedule coroutine and wait for result with timeout. Traces outcome."""
        fut = self.run_coroutine(coro)
        try:
            res = fut.result(timeout=timeout)
            try:
                append_trace({"event": "bridge_result_ok", "rows": getattr(res, '__len__', lambda: None)() if hasattr(res, '__len__') else None})
            except Exception:
                pass
            return res
        except Exception as e:
            try:
                append_trace({"event": "bridge_result_error", "error": str(e)})
            except Exception:
                pass
            raise


# Module-level global bridge (lazy)
_GLOBAL_BRIDGE: Optional[AsyncIBBridge] = None


def get_global_bridge(start: bool = True, **kwargs) -> Optional[AsyncIBBridge]:
    """Return a global AsyncIBBridge singleton, starting it if necessary."""
    global _GLOBAL_BRIDGE
    if _GLOBAL_BRIDGE is None:
        try:
            _GLOBAL_BRIDGE = AsyncIBBridge(**kwargs)
            if start:
                try:
                    _GLOBAL_BRIDGE.start()
                except Exception:
                    pass
        except Exception:
            _GLOBAL_BRIDGE = None
    return _GLOBAL_BRIDGE


