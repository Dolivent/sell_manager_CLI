"""Async IB bridge: runs an asyncio event loop in a dedicated thread and owns an IB() instance.

This allows worker threads to schedule async IB coroutines via
`asyncio.run_coroutine_threadsafe(...)` safely and avoid "no event loop in thread" errors.
"""
import asyncio
import threading
import time
from typing import Optional

try:
    from ib_insync import IB
except Exception:
    IB = None  # allow tests/machines without ib_insync


class AsyncIBBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.ib: Optional[IB] = None
        self._started = threading.Event()
        self._stopping = threading.Event()

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
                    # perform connect (blocking) so IB is ready for async calls
                    try:
                        self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=10)
                    except Exception:
                        # swallow; callers should handle failures via requests
                        pass
            finally:
                self._started.set()

            try:
                self.loop.run_forever()
            finally:
                # cleanup on exit
                try:
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
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


