from qtpy import QtWidgets, QtCore
from qtpy.QtGui import QColor, QBrush, QIntValidator
from .assigned_ma import AssignedMAStore
from .ib_worker import IBWorker
from pathlib import Path
import json
import time as time_mod
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo


class PositionsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Ensure assigned store exists early so load_assigned can read CSV immediately
        try:
            self.assigned_store = AssignedMAStore()
        except Exception:
            self.assigned_store = None
        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget(0, 9, self)
        headers = [
            "Ticker", "Qty", "Price", "MA Type", "MA Length", "Timeframe",
            "Strategy", "Status", "Last Signal"
        ]
        self.table.setHorizontalHeaderLabels(headers)
        # Prevent editing of item cells directly (we use widgets for editable fields)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        # (Order placement is handled from other UI flows; no direct place button)
        # Snapshot info area (single-line: left = time, right = status)
        snap_h = QtWidgets.QHBoxLayout()
        self.snapshot_label = QtWidgets.QLabel("Last snapshot: <none>")
        self.snapshot_label.setStyleSheet("padding:4px; font-weight:600; font-size:11px;")
        self.snapshot_warn = QtWidgets.QLabel("")  # tickers that would be closed
        self.snapshot_warn.setStyleSheet("padding:4px; font-size:11px;")
        snap_h.addWidget(self.snapshot_label)
        snap_h.addStretch()
        snap_h.addWidget(self.snapshot_warn, 0, QtCore.Qt.AlignRight)
        layout.addLayout(snap_h)
        # timer to refresh minute-snapshot info
        self._snapshot_timer = QtCore.QTimer(self)
        self._snapshot_timer.setInterval(30_000)
        self._snapshot_timer.timeout.connect(self.update_minute_snapshot_info)
        self._snapshot_timer.start()
        # whether to include pre/post-market signals in positions view (default False)
        self._show_premarket = False
        # file watcher for minute_snapshot to update immediately on append
        try:
            from qtpy.QtCore import QFileSystemWatcher
            self._fs_watcher = QFileSystemWatcher(self)
            # determine path
            try:
                am = AssignedMAStore()
                config_dir = am.path.parent
                project_root = config_dir.parent
                snap_path = str(project_root / "logs" / "minute_snapshot.jsonl")
            except Exception:
                snap_path = str(Path(__file__).resolve().parents[3] / "logs" / "minute_snapshot.jsonl")
            if Path(snap_path).exists():
                try:
                    self._fs_watcher.addPath(snap_path)
                    self._fs_watcher.fileChanged.connect(lambda p=snap_path: self.update_minute_snapshot_info())
                except Exception:
                    pass
            # watch assigned_ma.csv for external edits and reload assignments
            try:
                ass_path = str(am.path)
                if Path(ass_path).exists():
                    try:
                        self._fs_watcher.addPath(ass_path)
                        self._fs_watcher.fileChanged.connect(lambda p=ass_path: self._on_assigned_changed())
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            return
        except Exception:
            self._fs_watcher = None
        # ensure we have an AssignedMAStore and populate table now
        try:
            self.assigned_store = AssignedMAStore()
        except Exception:
            self.assigned_store = None
        try:
            if self.assigned_store:
                self.load_assigned()
        except Exception:
            pass

    def _on_assigned_changed(self):
        # reload assignments from file (debounce briefly)
        QtCore.QTimer.singleShot(200, self.load_assigned)

    def on_signals_updated(self, latest_map):
        """Receive latest signals mapping from SignalsWidget and refresh status column."""
        try:
            self.latest_signals = latest_map or {}
            # update status cells for matching tickers
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if not item:
                    continue
                ticker = item.text()
                entry = self.latest_signals.get(ticker) or self.latest_signals.get(ticker.split(":")[-1])
                if not entry:
                    # unknown -> gray
                    self._set_status_for_row(r, "Unknown", QColor("lightgray"))
                else:
                    decision = str(entry.get("decision", "") or "")
                    if decision.strip().lower() == "sellsignal":
                        self._set_status_for_row(r, "SellSignal", QColor("red"))
                    elif decision.strip().lower() == "nosignal":
                        self._set_status_for_row(r, "NoSignal", QColor("green"))
                    else:
                        self._set_status_for_row(r, decision or "Pending", QColor("yellow"))
        except Exception:
            return

    def set_show_premarket(self, val: bool):
        """Enable or disable inclusion of pre/post-market signals for Positions view."""
        try:
            self._show_premarket = bool(val)
            # refresh view immediately
            try:
                self.load_assigned()
            except Exception:
                pass
        except Exception:
            pass

    def _set_status_for_row(self, row_index: int, text: str, color: QColor):
        try:
            itm = self.table.item(row_index, 7)
            if itm is None:
                itm = QtWidgets.QTableWidgetItem(text)
                itm.setFlags(itm.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(row_index, 7, itm)
            itm.setText(text)
            itm.setBackground(color)
        except Exception:
            pass

    def load_assigned(self):
        rows = list(self.assigned_store.iter_rows())
        self.table.setRowCount(len(rows))
        # try load recent signals to populate price/last-signal columns
        try:
            am = AssignedMAStore()
            config_dir = am.path.parent
            project_root = config_dir.parent
            signals_path = project_root / "logs" / "signals.jsonl"
            latest = {}
            if signals_path.exists():
                with signals_path.open("r", encoding="utf-8") as f:
                    for ln in f:
                        try:
                            j = json.loads(ln)
                            t = j.get("ticker") or j.get("symbol")
                            if not t:
                                continue
                            # prefer 'ts' but accept 'time'
                            ts_raw = j.get("ts") or j.get("time") or ""
                            if not ts_raw:
                                continue
                            # parse timestamp and normalize to NY timezone
                            try:
                                dt = datetime.fromisoformat(ts_raw)
                            except Exception:
                                # skip unparsable timestamps
                                continue
                            try:
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
                            except Exception:
                                pass
                            try:
                                dt_ny = dt.astimezone(ZoneInfo("America/New_York"))
                            except Exception:
                                dt_ny = dt

                            # filter to US market hours:
                            # - default view: 09:30..16:00 (inclusive)
                            # - pre/post-market view enabled: 04:00..20:00 (inclusive)
                            try:
                                tpart = dt_ny.time()
                                if getattr(self, "_show_premarket", False):
                                    if (tpart < dt_time(4, 0)) or (tpart > dt_time(20, 0)):
                                        # outside pre/post-market window -> ignore for positions status
                                        continue
                                else:
                                    if (tpart < dt_time(9, 30)) or (tpart > dt_time(16, 0)):
                                        # outside regular market hours -> ignore for positions status
                                        continue
                            except Exception:
                                continue

                            # keep latest by timestamp (use normalized ISO string)
                            prev = latest.get(t)
                            ts_iso = dt_ny.isoformat()
                            if prev is None or (ts_iso and prev.get("ts") and ts_iso > prev.get("ts")):
                                latest[t] = {"ts": ts_iso, "close": j.get("close"), "decision": j.get("decision")}
                        except Exception:
                            continue
        except Exception:
            latest = {}
        for r_i, row in enumerate(rows):
            ticker = row.get("ticker") or ""
            ma_type = row.get("type") or ""
            # preserve blanks from CSV: do not default to 20
            length = row.get("length") or ""
            # preserve blanks from CSV for timeframe
            timeframe = row.get("timeframe") or ""
            # fill cells
            self.table.setItem(r_i, 0, QtWidgets.QTableWidgetItem(ticker))
            # set non-editable items for ticker, qty, price, status, last signal
            item_ticker = QtWidgets.QTableWidgetItem(ticker)
            item_ticker.setFlags(QtWidgets.QTableWidgetItem(item_ticker).flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r_i, 0, item_ticker)
            item_qty = QtWidgets.QTableWidgetItem("0")
            item_qty.setFlags(item_qty.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r_i, 1, item_qty)  # Qty
            item_price = QtWidgets.QTableWidgetItem("")
            item_price.setFlags(item_price.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r_i, 2, item_price)  # Price

            # MA Type dropdown
            ma_type_widget = QtWidgets.QComboBox()
            # allow empty (unassigned) MA type
            ma_type_widget.addItem("")
            ma_type_widget.addItems(["SMA", "EMA"])
            try:
                ma_type_widget.setCurrentText(ma_type if ma_type else "")
            except Exception:
                ma_type_widget.setCurrentText(ma_type or "")
            self.table.setCellWidget(r_i, 3, ma_type_widget)

            # use QLineEdit for length to allow blank display when unassigned
            length_widget = QtWidgets.QLineEdit()
            length_widget.setValidator(QIntValidator(0, 500))
            length_widget.setMaximumWidth(80)
            try:
                if length and str(length).strip():
                    length_widget.setText(str(int(length)))
                else:
                    length_widget.setText("")
            except Exception:
                length_widget.setText("")
            self.table.setCellWidget(r_i, 4, length_widget)

            timeframe_widget = QtWidgets.QComboBox()
            # allow empty timeframe to represent unassigned
            timeframe_widget.addItem("")
            timeframe_widget.addItems(["30m", "1H", "1D"])
            try:
                timeframe_widget.setCurrentText(timeframe if timeframe else "")
            except Exception:
                timeframe_widget.setCurrentText(timeframe or "")
            self.table.setCellWidget(r_i, 5, timeframe_widget)

            strategy_widget = QtWidgets.QComboBox()
            strategy_widget.addItems(["Market", "Market+StopLow"])
            self.table.setCellWidget(r_i, 6, strategy_widget)
            # connect change signals to save handler
            ma_type_widget.currentTextChanged.connect(lambda _t, row=r_i: self._on_cell_changed(row))
            length_widget.textChanged.connect(lambda _t, row=r_i: self._on_cell_changed(row))
            timeframe_widget.currentTextChanged.connect(lambda _t, row=r_i: self._on_cell_changed(row))
            strategy_widget.currentTextChanged.connect(lambda _t, row=r_i: self._on_cell_changed(row))

            status_item = QtWidgets.QTableWidgetItem("Unknown")
            status_item.setBackground(QColor("lightgray"))
            status_item.setFlags(status_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r_i, 7, status_item)

            last_item = QtWidgets.QTableWidgetItem("")
            last_item.setFlags(last_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r_i, 8, last_item)
            # populate price / last signal from latest signals if available
            if ticker and latest.get(ticker):
                try:
                    self.table.item(r_i, 2).setText(str(latest[ticker].get("close", "")))
                    ts = latest[ticker].get("ts", "")
                    try:
                        dt = datetime.fromisoformat(ts)
                        # format for positions: HH:MM:SS YYYY-MM-DD
                        formatted = dt.strftime("%H:%M:%S %Y-%m-%d")
                    except Exception:
                        formatted = ts or ""
                    self.table.item(r_i, 8).setText(formatted)
                except Exception:
                    pass
            # populate qty/price/status from latest minute snapshot if available (fast startup view)
            try:
                # populate qty/price from latest minute snapshot (fast startup view).
                # Do NOT derive or override the status column here — status should be set from
                # evaluated signals (hourly/daily) so the Positions status reflects the 3pm/hourly decision.
                from ..signal_generator import read_latest_minute_snapshot
                ms_rows = read_latest_minute_snapshot()
                for rr in ms_rows:
                    t = (rr.get("ticker") or rr.get("symbol") or "").strip()
                    if not t:
                        continue
                    if t == ticker or t.split(":")[-1] == ticker.split(":")[-1]:
                        # set qty/position
                        pos = rr.get("position")
                        try:
                            if pos is not None:
                                self.table.item(r_i, 1).setText(str(int(pos)) if float(pos).is_integer() else str(pos))
                        except Exception:
                            try:
                                self.table.item(r_i, 1).setText(str(pos))
                            except Exception:
                                pass
                        # set price from last_close
                        try:
                            last_close = rr.get("last_close")
                            if last_close is not None:
                                self.table.item(r_i, 2).setText(str(last_close))
                        except Exception:
                            pass
                        break
            except Exception:
                pass
            # set initial status from latest decision if available
            try:
                entry = latest.get(ticker) or latest.get(ticker.split(":")[-1])
                if entry:
                    decision = str(entry.get("decision", "") or "")
                    if decision.strip().lower() == "sellsignal":
                        self._set_status_for_row(r_i, "SellSignal", QColor("red"))
                    elif decision.strip().lower() == "nosignal":
                        self._set_status_for_row(r_i, "NoSignal", QColor("green"))
                    else:
                        self._set_status_for_row(r_i, decision or "Pending", QColor("yellow"))
            except Exception:
                pass
        # initial snapshot info populate
        try:
            self.update_minute_snapshot_info()
        except Exception:
            pass

    def update_minute_snapshot_info(self):
        """Read latest minute_snapshot.jsonl and display snapshot time and tickers that would be closed."""
        try:
            am = AssignedMAStore()
            config_dir = am.path.parent
            project_root = config_dir.parent
            snap_path = project_root / "logs" / "minute_snapshot.jsonl"
            if not snap_path.exists():
                self.snapshot_label.setText("Last snapshot: <none>")
                self.snapshot_warn.setText("")
                return
            # Prefer a daily (end-of-day) snapshot if present: search backwards for the most recent
            # snapshot whose start_ts/end_ts falls exactly on 16:00 NY time. If not found, fall back
            # to the last snapshot entry.
            last_obj = None
            with snap_path.open("r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if not lines:
                self.snapshot_label.setText("Last snapshot: <none>")
                self.snapshot_warn.setText("")
                return
            obj = None
            for ln in reversed(lines):
                try:
                    candidate = json.loads(ln)
                except Exception:
                    continue
                ts_raw = candidate.get("start_ts") or candidate.get("end_ts") or ""
                try:
                    dt = datetime.fromisoformat(ts_raw)
                except Exception:
                    dt = None
                try:
                    if dt is not None and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
                    if dt is not None:
                        dt_ny = dt.astimezone(ZoneInfo("America/New_York"))
                    else:
                        dt_ny = None
                except Exception:
                    dt_ny = dt
                # pick the first candidate that is an end-of-day snapshot (16:00 NY)
                try:
                    if dt_ny is not None and dt_ny.hour == 16 and dt_ny.minute == 0:
                        obj = candidate
                        break
                except Exception:
                    pass
            # fallback to the last snapshot if no EOD snapshot found
            if obj is None:
                try:
                    obj = json.loads(lines[-1])
                except Exception:
                    obj = None
            if not obj:
                self.snapshot_label.setText("Last snapshot: <none>")
                self.snapshot_warn.setText("")
                return
            start_ts = obj.get("start_ts") or obj.get("end_ts") or ""
            rows = obj.get("rows") or []
            # format end_ts for display: HH:MM:SS YYYY-MM-DD
            try:
                dt = datetime.fromisoformat(start_ts)
                formatted = dt.strftime("%H:%M:%S %Y-%m-%d")
            except Exception:
                formatted = start_ts or "<unknown>"
            self.snapshot_label.setText(f"Last snapshot: {formatted}")
            # compute tickers that would be closed: last_close < ma_value
            to_close = []
            for r in rows:
                try:
                    tk = r.get("ticker") or r.get("symbol")
                    last_close = r.get("last_close")
                    ma_val = r.get("ma_value")
                    if last_close is None or ma_val is None:
                        continue
                    try:
                        if float(last_close) < float(ma_val):
                            to_close.append(str(tk))
                    except Exception:
                        continue
                except Exception:
                    continue
            if to_close:
                self.snapshot_warn.setText("Would close: " + ", ".join(to_close))
                self.snapshot_warn.setStyleSheet("color: red; padding:6px;")
            else:
                self.snapshot_warn.setText("No tickers would be closed at snapshot price.")
                self.snapshot_warn.setStyleSheet("color: green; padding:6px;")
        except Exception:
            # fallback: clear
            self.snapshot_label.setText("Last snapshot: <error>")
            self.snapshot_warn.setText("")
            return

    def on_positions_update(self, positions):
        # positions is expected as list of dicts with 'symbol_full','symbol','qty','price'
        # Match by full token (EXCHANGE:SYM) or by symbol-only, case-insensitive.
        def norm(s: str) -> str:
            return (s or "").strip().upper()

        for pos in positions:
            pos_full = norm(pos.get("symbol_full") or pos.get("symbol") or "")
            pos_sym = norm(pos.get("symbol") or "")
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if not item:
                    continue
                ticker = item.text()
                tick_full = norm(ticker)
                tick_sym = tick_full.split(":")[-1]

                matched = False
                # exact full match
                if pos_full and pos_full == tick_full:
                    matched = True
                else:
                    # symbol-only match
                    if pos_sym and pos_sym == tick_sym:
                        matched = True
                    else:
                        # handle case where pos_full is like 'NASDAQ:TSLA' and ticker is 'TSLA'
                        if ":" in pos_full and tick_sym == pos_full.split(":")[-1]:
                            matched = True

                if matched:
                    try:
                        self.table.item(r, 1).setText(str(int(pos.get("qty", 0))))
                    except Exception:
                        try:
                            self.table.item(r, 1).setText(str(pos.get("qty", 0)))
                        except Exception:
                            pass
                    try:
                        price = pos.get("price")
                        if price is not None:
                            self.table.item(r, 2).setText(str(price))
                    except Exception:
                        pass

    def _on_cell_changed(self, row_index: int):
        # write the changed table back to assigned_ma
        try:
            rows = []
            for r in range(self.table.rowCount()):
                ticker = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
                ma_type_w = self.table.cellWidget(r, 3)
                length_w = self.table.cellWidget(r, 4)
                timeframe_w = self.table.cellWidget(r, 5)
                # read length from QLineEdit (allow blank)
                try:
                    if isinstance(length_w, QtWidgets.QLineEdit):
                        length_val = length_w.text().strip()
                    else:
                        # fallback for spinbox
                        length_val = str(length_w.value() if length_w else "")
                except Exception:
                    length_val = ""

                rows.append({
                    "ticker": ticker,
                    "type": ma_type_w.currentText() if ma_type_w and ma_type_w.currentText() else "",
                    "length": length_val,
                    "timeframe": timeframe_w.currentText() if timeframe_w and timeframe_w.currentText() else "",
                })
            self.assigned_store.write_rows(rows)
        except Exception:
            # avoid crashing UI on save errors
            return

    # Order placement UI removed; keep widget focused on display and MA editing.


class SignalsWidget(QtWidgets.QWidget):
    # emit latest per-ticker decisions to other widgets
    signals_updated = QtCore.Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        # Table view: first column = Time, remaining columns = tickers
        self.table = QtWidgets.QTableWidget(0, 0, self)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        # Derive signals path
        try:
            am = AssignedMAStore()
            config_dir = am.path.parent
            project_root = config_dir.parent
            self.signals_path = project_root / "logs" / "signals.jsonl"
        except Exception:
            self.signals_path = Path(__file__).resolve().parents[3] / "logs" / "signals.jsonl"

        self._last_size = 0
        self._tail_timer = QtCore.QTimer(self)
        self._tail_timer.setInterval(1500)
        self._tail_timer.timeout.connect(self._poll_signals)
        self._tail_timer.start()
        # whether to include pre/post-market signals (default False)
        self._show_premarket = False
        # cache of tickers with positions from the latest minute snapshot;
        # used so we continue showing only position tickers even when a transient
        # snapshot read returns no rows.
        self._last_pos_set = set()

    def _poll_signals(self):
        try:
            if not self.signals_path.exists():
                return
            # read recent file content
            with self.signals_path.open("r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if not lines:
                return
            # take last N lines for matrix
            recent = lines[-500:]
            # Step 1: Remove exact duplicate lines (identical JSON)
            seen_raw = set()
            unique_lines = []
            for ln in recent:
                if ln in seen_raw:
                    continue
                seen_raw.add(ln)
                unique_lines.append(ln)
            
            # Step 2: Collect all signals, parse timestamps, normalize to NY, filter by market hours
            # Structure: raw_signals[(ts_hour, ticker)] = [decision1, decision2, ...]
            # Group by hour: truncate to hour (or 09:30 for the opening hour)
            raw_signals = {}  # mapping (ts_hour, ticker) -> list of decisions
            tickers = {}
            times = {}  # mapping ts_hour -> datetime
            
            def truncate_to_hour(dt_ny):
                """Map a timestamp to the UI bucket *end* time.
                Rules:
                - For timestamps between 09:30..09:59 => bucket_end = 10:00
                - Porosity allowance: timestamps within POROSITY_SECONDS (30s) after the exact hour
                  (minute==0 and second<=30) map to the current hour bucket (previous bucket_end).
                  This accounts for processing delays where signals generated just after the hour
                  should be grouped with the previous hour's bucket.
                - Otherwise bucket_end = ceil to next hour (even exact hour goes to next hour),
                  so column '11:00' represents 10:00..10:59.
                - Allow mapping of timestamps up to 16:00:59 into the 16:00 bucket.
                """
                POROSITY_SECONDS = 30
                # special-case 09:30..09:59 -> 10:00
                if dt_ny.hour == 9 and dt_ny.minute >= 30:
                    return dt_ny.replace(hour=10, minute=0, second=0, microsecond=0)
                # porosity check: if timestamp is within POROSITY_SECONDS after exact hour,
                # map to current hour bucket (previous bucket_end)
                if dt_ny.minute == 0 and dt_ny.second <= POROSITY_SECONDS:
                    # map to current hour bucket (e.g., 11:00:03 -> 11:00 bucket)
                    return dt_ny.replace(minute=0, second=0, microsecond=0)
                # ceil to next hour (even exact hour -> next hour)
                base_hour = dt_ny.replace(minute=0, second=0, microsecond=0)
                bucket_end = base_hour + timedelta(hours=1)
                # if bucket_end would be >16:00 but ts is within allowed post-close window, map to 16:00
                try:
                    if bucket_end.hour > 16:
                        if dt_ny.time() <= dt_time(16, 0, 59):
                            return dt_ny.replace(hour=16, minute=0, second=0, microsecond=0)
                except Exception:
                    pass
                return bucket_end
            
            for ln in unique_lines:
                try:
                    j = json.loads(ln)
                    ticker = (j.get("ticker") or j.get("symbol") or "").strip()
                    ts_raw = j.get("ts") or j.get("time") or ""
                    decision = j.get("decision") or ""
                    if not ticker or not ts_raw:
                        continue
                    # parse timestamp
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                    except Exception:
                        # skip unparsable timestamps
                        continue
                    # ensure we interpret naive timestamps as America/New_York
                    try:
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
                    except Exception:
                        pass

                    # normalize to NY timezone for consistent market-hour checks
                    try:
                        dt_ny = dt.astimezone(ZoneInfo("America/New_York"))
                    except Exception:
                        dt_ny = dt

                    # filter to US market hours:
                    # - default view: 09:30..16:00 (inclusive)
                    # - pre/post-market view enabled: 04:00..20:00 (inclusive)
                    try:
                        tpart = dt_ny.time()
                        if getattr(self, "_show_premarket", False):
                            # include pre/post-market windows only between 04:00 and 20:30
                            if (tpart < dt_time(4, 0)) or (tpart > dt_time(20, 30, 59)):
                                continue
                        else:
                            # allow a small post-close window up to 16:00:59 so post-close signals
                            # (e.g. 16:00:01) can be captured into the 16:00 bucket
                            if (tpart < dt_time(9, 30)) or (tpart > dt_time(16, 0, 59)):
                                continue
                    except Exception:
                        # if time parse fails, skip the row
                        continue

                    # truncate to hour bucket (09:30:00 for 9:30-9:59, or HH:00:00 for other hours)
                    dt_hour = truncate_to_hour(dt_ny)
                    ts_hour = dt_hour.isoformat()

                    # collect ticker and timestamp
                    tickers[ticker] = True
                    times[ts_hour] = dt_hour
                    
                    # collect all decisions for this (ticker, ts_hour) bucket
                    key = (ts_hour, ticker)
                    if key not in raw_signals:
                        raw_signals[key] = []
                    # store decision with its original normalized timestamp so we can
                    # later choose the most recent decision for that (ts_hour, ticker)
                    raw_signals[key].append({"decision": decision, "ts": dt_ny.isoformat()})
                except Exception:
                    continue
            
            # Step 3: Merge decisions per (ticker, ts_hour) bucket.
            # Current behavior: latest-wins (most recent decision by timestamp).
            # For multiple non-NoSignal decisions, the implementation falls back to
            # a precedence-based approach only if timestamp comparison fails.
            decisions = {}  # mapping ts_hour -> {ticker: merged_decision}
            
            def merge_decisions(decision_list):
                """Merge a list of decision entries into a single decision for the bucket.
                Deterministic precedence: SellSignal > NoSignal > Skip.
                Each item in decision_list may be a dict with keys 'decision' and optional 'ts',
                or a plain string. Return canonical decision string.
                """
                if not decision_list:
                    return "NoSignal"
                try:
                    # normalize decision strings from entries
                    norms = []
                    for d in decision_list:
                        try:
                            if isinstance(d, dict):
                                dec = (d.get("decision") or "").strip()
                            else:
                                dec = str(d).strip()
                            norms.append(dec)
                        except Exception:
                            continue

                    # precedence-based selection
                    lowered = [s.lower() for s in norms if s]
                    if any(s == "sellsignal" for s in lowered):
                        return "SellSignal"
                    if any(s == "nosignal" for s in lowered):
                        return "NoSignal"
                    if any(s == "skip" for s in lowered):
                        return "Skip"

                    # fallback: choose the most recent by ts if available
                    try:
                        latest = max(
                            (d for d in decision_list if isinstance(d, dict) and (d.get("ts") or "")),
                            key=lambda d: d.get("ts") or ""
                        )
                        return (latest.get("decision") or "NoSignal")
                    except Exception:
                        # final fallback: return first non-empty normalized value or NoSignal
                        for s in norms:
                            if s:
                                return s
                        return "NoSignal"
                except Exception:
                    return "NoSignal"
            
            for (ts_hour, ticker), decision_list in raw_signals.items():
                merged = merge_decisions(decision_list)
                # Determine display key: use the bucket end time (ts_hour) as the display key.
                # This aligns displayed row labels (e.g., 16:00) with the decisions generated for that bucket.
                # The opening-period mapping (09:30..09:59 -> 10:00) is naturally represented
                # by the bucket end time, so no additional shift is required.
                try:
                    display_key = ts_hour
                except Exception:
                    display_key = ts_hour
                bucket = decisions.setdefault(display_key, {})
                bucket[ticker] = merged

            if not tickers or not times:
                return

            # augment times with market-hour rows (09:30, 10:00, 11:00, ..., 16:00) for each date present
            generated_times = set()
            try:
                dates = set(dt.date() for dt in times.values())
            except Exception:
                dates = set()
            for d in dates:
                try:
                    # create rows covering the displayed window.
                    # - default view: create 10:00..16:00 (market hours middle)
                    # - pre/post-market view: create 05:00..21:00 so buckets represent 04:00..20:59
                    if getattr(self, "_show_premarket", False):
                        hours = list(range(5, 22))  # 05,06,...,21 -> buckets representing 04:00..20:59
                    else:
                        hours = list(range(10, 17))  # 10,11,...,16
                    for hr in hours:
                        minute = 0
                        dt_hour = datetime(d.year, d.month, d.day, hr, minute, 0, tzinfo=ZoneInfo("America/New_York"))
                        dt_hour = dt_hour.replace(microsecond=0)
                        ts_hour = dt_hour.isoformat()
                        if ts_hour not in times:
                            times[ts_hour] = dt_hour
                            generated_times.add(ts_hour)
                except Exception:
                    continue

            # sort times newest-first
            times_list = sorted(times.keys(), reverse=True)
            tickers_list = list(tickers.keys())

            # filter tickers to only those with current positions (from minute_snapshot)
            try:
                from ..signal_generator import read_latest_minute_snapshot
                ms_rows = read_latest_minute_snapshot()
                pos_set = set()
                for r in ms_rows:
                    try:
                        t = (r.get("ticker") or r.get("symbol") or "").strip()
                        if not t:
                            continue
                        pos = float(r.get("position", 0) or 0)
                        if pos != 0:
                            pos_set.add(t)
                            pos_set.add(t.split(":")[-1])
                    except Exception:
                        continue
                # If we got a non-empty snapshot, remember the pos_set and filter to it.
                if pos_set:
                    self._last_pos_set = pos_set
                    tickers_list = [t for t in tickers_list if (t in pos_set) or (t.split(":")[-1] in pos_set)]
                else:
                    # snapshot empty: attempt to derive positions from recent signals (fallback)
                    try:
                        sig_pos_set = set()
                        # self.signals_path was set in __init__ to the signals.jsonl file
                        if getattr(self, "signals_path", None) and self.signals_path.exists():
                            with self.signals_path.open("r", encoding="utf-8") as sf:
                                # read from end to find latest position entries quickly
                                lines = [ln.strip() for ln in sf if ln.strip()]
                            for ln in reversed(lines[-2000:]):  # limit scan to last 2000 lines
                                try:
                                    j = json.loads(ln)
                                except Exception:
                                    continue
                                tk = (j.get("ticker") or j.get("symbol") or "").strip()
                                if not tk:
                                    continue
                                try:
                                    pos = float(j.get("position", 0) or 0)
                                except Exception:
                                    pos = 0
                                if pos != 0:
                                    sig_pos_set.add(tk)
                                    sig_pos_set.add(tk.split(":")[-1])
                            # if we derived a set from signals, use it and cache
                            if sig_pos_set:
                                self._last_pos_set = sig_pos_set
                                tickers_list = [t for t in tickers_list if (t in sig_pos_set) or (t.split(":")[-1] in sig_pos_set)]
                            else:
                                # fallback to last known pos_set if available
                                if getattr(self, "_last_pos_set", None):
                                    tickers_list = [t for t in tickers_list if (t in self._last_pos_set) or (t.split(":")[-1] in self._last_pos_set)]
                                else:
                                    # no snapshot ever observed -> show no tickers (only Time column)
                                    tickers_list = []
                    except Exception:
                        if getattr(self, "_last_pos_set", None):
                            tickers_list = [t for t in tickers_list if (t in self._last_pos_set) or (t.split(":")[-1] in self._last_pos_set)]
                        else:
                            tickers_list = []
            except Exception:
                # if snapshot read fails, fall back to last known pos set or show none
                if getattr(self, "_last_pos_set", None):
                    tickers_list = [t for t in tickers_list if (t in self._last_pos_set) or (t.split(":")[-1] in self._last_pos_set)]
                else:
                    tickers_list = []

            # build table: columns = 1 + len(tickers)
            self.table.clear()
            self.table.setColumnCount(1 + len(tickers_list))
            headers = ["Time"] + tickers_list
            self.table.setHorizontalHeaderLabels(headers)
            self.table.setRowCount(len(times_list))

            # build display rows with blank separators when day changes
            display_rows = []
            prev_date = None
            for ts in times_list:
                try:
                    dt = datetime.fromisoformat(ts)
                    date_only = dt.strftime("%Y-%m-%d")
                    # Display ranges should show the bucket that ends at the column time:
                    # - 10:00 => 09:30–09:59
                    # - HH:00 => (HH-1):00–(HH-1):59
                    try:
                        if dt.minute == 0:
                            # the displayed label is the end-of-bucket time (dt),
                            # so the range is the previous hour (or 09:30..09:59 for 10:00)
                            if dt.hour == 10:
                                range_start = dt.replace(hour=9, minute=30, second=0, microsecond=0)
                                range_end = dt.replace(hour=9, minute=59, second=59, microsecond=0)
                            else:
                                range_start = (dt - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                                range_end = dt - timedelta(seconds=1)
                        else:
                            # fallback: show dt..dt+hour-1s
                            range_start = dt
                            range_end = dt + timedelta(hours=1) - timedelta(seconds=1)
                        # special label for market close column (16:00)
                        if dt.hour == 16 and dt.minute == 0:
                            range_label = "15:00–15:59 (market close)"
                        else:
                            rs = range_start.strftime("%H:%M")
                            re = range_end.strftime("%H:%M")
                            range_label = f"{rs}–{re}"
                    except Exception:
                        range_label = ""
                    formatted_ts = f"{date_only} {dt.strftime('%H:%M:%S')}" + (f" ({range_label})" if range_label else "")
                except Exception:
                    formatted_ts = ts
                    date_only = None

                # insert blank separator when day changes (and not first row)
                if prev_date is not None and date_only is not None and date_only != prev_date:
                    display_rows.append(None)
                prev_date = date_only
                display_rows.append((ts, formatted_ts))

            self.table.setRowCount(len(display_rows))
            for r_i, entry in enumerate(display_rows):
                if entry is None:
                    # blank separator row: insert empty cells and clear row header (no numbering)
                    for c in range(self.table.columnCount()):
                        self.table.setItem(r_i, c, QtWidgets.QTableWidgetItem(""))
                    try:
                        self.table.setVerticalHeaderItem(r_i, QtWidgets.QTableWidgetItem(""))
                    except Exception:
                        pass
                    continue
                ts_raw, ts_fmt = entry
                time_item = QtWidgets.QTableWidgetItem(ts_fmt)
                time_item.setFlags(time_item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(r_i, 0, time_item)
                row_map = decisions.get(ts_raw, {})
                for c_i, ticker in enumerate(tickers_list, start=1):
                    decision = row_map.get(ticker, "")
                    # determine dt for this row
                    try:
                        row_dt = times.get(ts_raw)
                    except Exception:
                        row_dt = None
                    # current NY time
                    try:
                        now_ny = datetime.now(ZoneInfo("America/New_York"))
                    except Exception:
                        now_ny = None

                    # If this timestamp is a generated empty bucket OR it's a future bucket (relative to now),
                    # show 'no data' to indicate it hasn't triggered yet.
                    is_future = False
                    try:
                        if row_dt is not None and now_ny is not None and row_dt > now_ny:
                            is_future = True
                    except Exception:
                        is_future = False

                    if ((ts_raw in generated_times) or is_future) and not decision:
                        item = QtWidgets.QTableWidgetItem("no data")
                        item.setForeground(QBrush(QColor("gray")))
                    else:
                        if not decision or decision == "NoSignal":
                            display = "-"
                            item = QtWidgets.QTableWidgetItem(display)
                        else:
                            item = QtWidgets.QTableWidgetItem(str(decision))
                            if str(decision).strip().lower() == "sellsignal":
                                # red font
                                item.setForeground(QBrush(QColor("red")))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    self.table.setItem(r_i, c_i, item)
            # scale columns to their contents
            try:
                self.table.resizeColumnsToContents()
            except Exception:
                pass

            # update last known size
            try:
                size = self.signals_path.stat().st_size
                self._last_size = size
            except Exception:
                pass
            # build latest per-ticker map (most recent decision)
            try:
                latest_map = {}
                for ts in times_list:
                    bucket = decisions.get(ts, {})
                    for tk, dec in bucket.items():
                        if tk not in latest_map:
                            latest_map[tk] = {"decision": dec, "ts": ts}
                # emit latest mapping for other widgets
                try:
                    self.signals_updated.emit(latest_map)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            return

    def set_show_premarket(self, val: bool):
        """Enable or disable inclusion of pre/post-market signals."""
        try:
            self._show_premarket = bool(val)
            # refresh view immediately
            try:
                self._poll_signals()
            except Exception:
                pass
        except Exception:
            pass


class SettingsWidget(QtWidgets.QWidget):
    connection_toggled = QtCore.Signal(bool)
    show_premarket_toggled = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)
        self.host = QtWidgets.QLineEdit("127.0.0.1")
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(4001)
        self.client_id = QtWidgets.QSpinBox()
        self.client_id.setValue(1)
        self.live_checkbox = QtWidgets.QCheckBox("Live (send orders)")
        self.allow_auto_send = QtWidgets.QCheckBox("Allow auto-send (no confirmation)")
        self.allow_auto_send.setChecked(True)
        # show pre/post-market signals in the signals tab (default: False)
        self.show_premarket_checkbox = QtWidgets.QCheckBox("Show pre/post-market")
        self.show_premarket_checkbox.setChecked(False)
        # emit signal when toggled
        try:
            self.show_premarket_checkbox.toggled.connect(lambda v: self.show_premarket_toggled.emit(bool(v)))
        except Exception:
            pass
        self.status_indicator = QtWidgets.QLabel("●")
        self.status_indicator.setStyleSheet("color: gray; font-size: 18px;")

        # compact host/port/client id horizontal row (aligned top, constrained widths)
        row_h = QtWidgets.QHBoxLayout()
        lbl_host = QtWidgets.QLabel("Host")
        lbl_port = QtWidgets.QLabel("Port")
        lbl_cid = QtWidgets.QLabel("Client ID")
        self.host.setMaximumWidth(220)
        self.port.setMaximumWidth(90)
        self.client_id.setMaximumWidth(90)
        row_h.setAlignment(QtCore.Qt.AlignTop)
        row_h.addWidget(lbl_host, 0)
        row_h.addWidget(self.host, 0)
        row_h.addSpacing(8)
        row_h.addWidget(lbl_port, 0)
        row_h.addWidget(self.port, 0)
        row_h.addSpacing(8)
        row_h.addWidget(lbl_cid, 0)
        row_h.addWidget(self.client_id, 0)
        row_h.addStretch()
        layout.addRow(row_h)
        layout.addRow(self.allow_auto_send)
        layout.addRow(self.show_premarket_checkbox)
        # console log for pipeline/ib events
        self.console = QtWidgets.QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(200)
        layout.addRow(QtWidgets.QLabel("Logs"), self.console)
        # no auto-run control (pipeline auto-starts when IB connects)

        # connect button removed; use traffic light click to connect/disconnect

    def _on_connect_clicked(self):
        # emit connect request so the main application can handle connect
        # (connect button requests connection; status light can be used to disconnect)
        self.connection_toggled.emit(True)


