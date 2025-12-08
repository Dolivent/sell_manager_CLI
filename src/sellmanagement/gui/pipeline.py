from qtpy.QtCore import QObject, Signal
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class PipelineRunner(QObject):
    started = Signal()
    stopped = Signal()
    snapshot_done = Signal(object)  # emits (end_ts, rows)
    need_assign = Signal(list)

    def __init__(self, ib_worker, parent=None):
        super().__init__(parent)
        self._ib_worker = ib_worker
        self._thread = None
        self._running = False
        self._assign_event = None
        self._assign_timeout = 300.0
        self._last_missing_emitted = None
        self._missing_emit_cooldown = 60.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.started.emit()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(1.0)
            self._thread = None
        self.stopped.emit()

    def _run_loop(self):
        # requires IB client connected in ib_worker
        from ..minute_snapshot import run_minute_snapshot
        from ..signal_generator import generate_signals_from_rows

        while self._running:
            # wait until next top of minute in NY timezone
            now = datetime.now(tz=ZoneInfo("America/New_York"))
            next_min = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
            # special-case 16:00 wake earlier
            if next_min.hour == 16 and next_min.minute == 0:
                seconds_till_next = (next_min - now).total_seconds() - 5.0
            else:
                seconds_till_next = (next_min - now).total_seconds()
            if seconds_till_next < 0.1:
                seconds_till_next = 0.1
            slept = 0.0
            chunk = min(5.0, seconds_till_next)
            while self._running and slept + 0.0001 < seconds_till_next:
                to_sleep = min(chunk, seconds_till_next - slept)
                time.sleep(to_sleep)
                slept += to_sleep

            if not self._running:
                break

            # run one snapshot cycle (pre-sync, snapshot, optional signal eval)

            # run one snapshot cycle (pre-sync, snapshot, optional signal eval)
            try:
                try:
                    end_ts, rows = self.run_snapshot_once()
                except Exception:
                    # failure in snapshot; sleep briefly and continue loop
                    time.sleep(2.0)
                    continue
                # emit snapshot done (already emitted inside run_snapshot_once as well)
                try:
                    self.snapshot_done.emit((end_ts, rows))
                except Exception:
                    pass
            except Exception:
                time.sleep(2.0)
                continue

    def run_snapshot_once(self):
        """Run one full snapshot cycle: sync assignments, run snapshot, and optionally run signal eval.
        Returns (end_ts, rows).
        """
        from ..minute_snapshot import run_minute_snapshot
        from ..signal_generator import generate_signals_from_rows

        # pre-sync live positions and assignments on IB thread
        def _get_live_and_sync():
            try:
                from ..assign import sync_assignments_to_positions, get_assignments_list
                live_positions = []
                try:
                    raw = self._ib_worker._client.positions() or []
                    for p in raw:
                        try:
                            contract = getattr(p, 'contract', None) if not isinstance(p, dict) else p.get('contract')
                            if contract is None:
                                continue
                            symbol = getattr(contract, 'symbol', None) if not isinstance(contract, dict) else contract.get('symbol')
                            exchange = getattr(contract, 'exchange', None) if not isinstance(contract, dict) else contract.get('exchange')
                            if symbol:
                                live_positions.append(f"{exchange or 'SMART'}:{symbol}")
                        except Exception:
                            continue
                except Exception:
                    live_positions = []
                sync_res = sync_assignments_to_positions(live_positions)
                # detect missing assignments
                missing = []
                cur = get_assignments_list()
                for r in cur:
                    # consider missing only when type/length are not set (timeframe optional)
                    if not (r.get('type') and r.get('length')):
                        missing.append(r.get('ticker'))
                return sync_res, missing
            except Exception:
                return None, []

        sync_res, missing = self._ib_worker.run_on_thread(_get_live_and_sync, timeout=30)
        if missing:
            # dedupe missing and ignore entries that are already assigned now
            try:
                from ..assign import get_assignments_list
                cur = get_assignments_list()
                cur_set = set([r.get('ticker') for r in cur if r.get('ticker') and r.get('type') and r.get('length')])
                missing = [m for m in missing if m not in cur_set]
            except Exception:
                pass
            if missing:
                # Emit missing assignment notification every snapshot until assignments populated.
                try:
                    self.need_assign.emit(missing)
                except Exception:
                    pass

        # run the snapshot on IB thread
        def _run_snapshot():
            from ..assign import get_assignments_list
            rows = get_assignments_list()
            tickers = [r.get('ticker') for r in rows if r.get('ticker')]
            return run_minute_snapshot(self._ib_worker._client, tickers, concurrency=32)

        res = self._ib_worker.run_on_thread(_run_snapshot, timeout=300)
        end_ts, rows = res

        # optional signal evaluation
        try:
            ts_dt = datetime.fromisoformat(end_ts)
        except Exception:
            ts_dt = datetime.now(tz=ZoneInfo("America/New_York"))
        is_top_of_hour = (ts_dt.minute == 0)
        is_eod_prep = (ts_dt.hour == 15 and ts_dt.minute == 59 and ts_dt.second >= 55)
        evaluate_hourly = is_top_of_hour or is_eod_prep
        evaluate_daily = is_eod_prep
        if evaluate_hourly or evaluate_daily:
            try:
                def _gen():
                    return generate_signals_from_rows(rows, evaluate_hourly=evaluate_hourly, evaluate_daily=evaluate_daily, dry_run=True)
                _ = self._ib_worker.run_on_thread(_gen, timeout=120)
            except Exception:
                pass

        return end_ts, rows

    def confirm_assignments(self):
        """Called by GUI when user has provided assignments for previously-missing tickers."""
        try:
            if self._assign_event:
                self._assign_event.set()
        except Exception:
            pass

