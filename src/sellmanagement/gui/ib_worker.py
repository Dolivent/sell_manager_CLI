from qtpy.QtCore import QObject, Signal, QTimer
from concurrent.futures import ThreadPoolExecutor
from ..ib_client import IBClient
from pathlib import Path
import time
import logging
import threading
import queue
import asyncio

logger = logging.getLogger(__name__)


class IBWorker(QObject):
    connected = Signal(bool)
    positions_updated = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = IBClient()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(5000)
        self._poll_timer.timeout.connect(self._poll_positions)
        self._running = False
        # reconnect/backoff state
        self._backoff_seconds = 1
        self._max_backoff = 60
        self._reconnect_timer = None
        self._saved_conn_params = None
        self._consecutive_poll_errors = 0
        # dedicated IB thread / queue so all IB calls run on same thread (avoids event-loop conflicts)
        self._call_queue = queue.Queue()
        self._ib_thread = None

    def connect(self, host="127.0.0.1", port=4001, client_id=1):
        # run connect on the dedicated IB thread to ensure consistent event loop behavior
        def _do():
            try:
                self._client.host = host
                self._client.port = port
                self._client.client_id = client_id
                ok = self._client.connect()
                # success: reset backoff and cancel any pending reconnects
                self._backoff_seconds = 1
                if self._reconnect_timer:
                    try:
                        self._reconnect_timer.cancel()
                    except Exception:
                        pass
                    self._reconnect_timer = None
                self._saved_conn_params = (host, port, client_id)
                self.connected.emit(True)
                self._running = True
                return ok
            except Exception:
                logger.exception("IBWorker.connect failed")
                self.connected.emit(False)
                # schedule reconnect with exponential backoff
                try:
                    backoff = min(self._backoff_seconds, self._max_backoff)
                    logger.info("Scheduling reconnect in %s seconds", backoff)
                    if self._reconnect_timer:
                        try:
                            self._reconnect_timer.cancel()
                        except Exception:
                            pass
                    self._reconnect_timer = threading.Timer(backoff, lambda: self._submit_to_ib_thread(_do))
                    self._reconnect_timer.daemon = True
                    self._reconnect_timer.start()
                    self._backoff_seconds = min(self._backoff_seconds * 2, self._max_backoff)
                except Exception:
                    logger.exception("Failed to schedule reconnect")
                return False

        # record desired params and start initial attempt
        self._saved_conn_params = (host, port, client_id)
        # ensure IB thread running
        if self._ib_thread is None:
            self._start_ib_thread()
        self._submit_to_ib_thread(_do)

    def disconnect(self):
        # Schedule the actual disconnect to run on the IB thread to avoid event-loop conflicts.
        def _do_disconnect():
            try:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
            finally:
                return

        try:
            # stop polling timer on main thread (safe to call here)
            try:
                if self._poll_timer.isActive():
                    self._poll_timer.stop()
            except Exception:
                pass

            # submit the disconnect to the IB thread if available, otherwise run in executor
            if self._ib_thread:
                self._submit_to_ib_thread(_do_disconnect)
                # schedule thread stop marker after disconnect attempt
                try:
                    self._call_queue.put(None)
                except Exception:
                    pass
            else:
                # no IB thread; run disconnect in executor
                try:
                    self._executor.submit(_do_disconnect)
                except Exception:
                    pass

        finally:
            self._running = False
            # emit disconnected status on main thread
            try:
                self.connected.emit(False)
            except Exception:
                pass
            # cancel any pending reconnect attempts
            if self._reconnect_timer:
                try:
                    self._reconnect_timer.cancel()
                except Exception:
                    pass
                self._reconnect_timer = None

    def _poll_positions(self):
        # background fetch
        def _fetch():
            try:
                pos = []
                raw = self._client.positions()
                # normalize into dicts expected by UI
                for p in raw:
                    try:
                        contract = getattr(p, 'contract', None) if not isinstance(p, dict) else p.get('contract')
                        # symbol and exchange may come from contract object or dict
                        if contract is None:
                            symbol = getattr(p, 'symbol', None) if not isinstance(p, dict) else p.get('symbol')
                            exchange = getattr(p, 'exchange', None) if not isinstance(p, dict) else p.get('exchange')
                        else:
                            symbol = getattr(contract, 'symbol', None) if not isinstance(contract, dict) else contract.get('symbol')
                            exchange = getattr(contract, 'exchange', None) if not isinstance(contract, dict) else contract.get('exchange')

                        if not symbol:
                            # skip invalid entries
                            continue

                        # construct full token if exchange present
                        if exchange:
                            sym_full = f"{exchange}:{symbol}"
                        else:
                            sym_full = str(symbol)

                        # quantity field can be named differently
                        qty = None
                        try:
                            qty = getattr(p, 'position', None) if not isinstance(p, dict) else p.get('position')
                            if qty is None:
                                qty = getattr(p, 'pos', None) if not isinstance(p, dict) else p.get('pos')
                        except Exception:
                            qty = None

                        # avg cost / price if available
                        price = None
                        try:
                            price = getattr(p, 'avgCost', None) if not isinstance(p, dict) else p.get('avgCost')
                        except Exception:
                            price = None

                        pos.append({
                            "symbol_full": sym_full,
                            "symbol": str(symbol),
                            "qty": float(qty) if qty is not None else 0.0,
                            "price": float(price) if price is not None else None,
                        })
                    except Exception:
                        # skip malformed position entry
                        continue
                # reset consecutive error counter on success
                self._consecutive_poll_errors = 0
                self.positions_updated.emit(pos)
            except Exception:
                # increment error counter and trigger reconnect if repeated failures
                self._consecutive_poll_errors += 1
                logger.exception("Error fetching positions (count=%s)", self._consecutive_poll_errors)
                if self._consecutive_poll_errors >= 3:
                    logger.info("Consecutive position errors exceeded threshold; scheduling reconnect")
                    try:
                        if self._saved_conn_params:
                            h, p, cid = self._saved_conn_params
                            self._submit_to_ib_thread(lambda: self.connect(host=h, port=p, client_id=cid))
                    except Exception:
                        logger.exception("Failed to schedule reconnect from poll errors")
                return

        # run fetch on IB thread so it shares same event loop/context as connect
        if self._ib_thread:
            self._submit_to_ib_thread(_fetch)
        else:
            self._executor.submit(_fetch)

    def _start_ib_thread(self):
        if self._ib_thread:
            return

        def _thread_func():
            # set up dedicated asyncio loop for IB if needed
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception:
                loop = None
            while True:
                try:
                    task = self._call_queue.get()
                    if task is None:
                        break
                    try:
                        # support tasks that are either callables or (callable, result_queue)
                        if isinstance(task, tuple) and len(task) == 2:
                            fn, res_q = task
                            try:
                                res = fn()
                                try:
                                    res_q.put((True, res))
                                except Exception:
                                    pass
                            except Exception as e:
                                try:
                                    res_q.put((False, e))
                                except Exception:
                                    pass
                        else:
                            # simple callable
                            task()
                    except Exception:
                        logger.exception("Error in IB thread function")
                except Exception:
                    logger.exception("IB thread main loop error")
            # cleanup loop if created
            try:
                if loop is not None:
                    loop.stop()
            except Exception:
                pass

        t = threading.Thread(target=_thread_func, daemon=True)
        t.start()
        self._ib_thread = t

    def _submit_to_ib_thread(self, fn):
        try:
            self._call_queue.put(fn)
        except Exception:
            logger.exception("Failed to submit function to IB thread")

    def run_on_thread(self, fn, timeout: float | None = None):
        """Run callable `fn` on the IB thread and return its result (or raise)."""
        if self._ib_thread is None:
            # ensure thread exists
            self._start_ib_thread()
        res_q = queue.Queue(maxsize=1)
        try:
            self._call_queue.put((fn, res_q))
            ok, payload = res_q.get(timeout=timeout)
            if ok:
                return payload
            else:
                raise payload
        except queue.Empty:
            raise TimeoutError("Timeout waiting for IB thread task result")
        except Exception:
            raise

    def shutdown(self, timeout: float = 2.0):
        """Attempt a clean shutdown: stop poll timer, disconnect IB client, stop IB thread."""
        try:
            # stop poll timer (should be main thread)
            try:
                if self._poll_timer.isActive():
                    self._poll_timer.stop()
            except Exception:
                pass

            # request disconnect and stop IB thread
            try:
                def _do_disconnect_and_stop():
                    try:
                        try:
                            self._client.disconnect()
                        except Exception:
                            pass
                    finally:
                        return

                if self._ib_thread:
                    self._submit_to_ib_thread(_do_disconnect_and_stop)
                    # push sentinel to stop loop after pending calls
                    try:
                        self._call_queue.put(None)
                    except Exception:
                        pass
                else:
                    # no dedicated thread, perform direct disconnect via executor
                    try:
                        self._executor.submit(lambda: self._client.disconnect())
                    except Exception:
                        pass
            except Exception:
                logger.exception("Error during IBWorker shutdown disconnect")

            # wait briefly for thread to exit
            try:
                if self._ib_thread:
                    self._ib_thread.join(timeout)
                    self._ib_thread = None
            except Exception:
                pass
        finally:
            try:
                self.connected.emit(False)
            except Exception:
                pass

 