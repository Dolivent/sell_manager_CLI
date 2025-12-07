from qtpy import QtWidgets, QtCore
from qtpy.QtGui import QColor, QBrush
from .assigned_ma import AssignedMAStore
from .ib_worker import IBWorker
from pathlib import Path
import json
import time
from datetime import datetime


class PositionsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        # Snapshot info area (last snapshot time + tickers that would be closed)
        self.snapshot_label = QtWidgets.QLabel("Last snapshot: <none>")
        self.snapshot_label.setStyleSheet("padding:6px; font-weight:600;")
        self.snapshot_warn = QtWidgets.QLabel("")  # tickers that would be closed
        self.snapshot_warn.setStyleSheet("padding:6px;")
        layout.addWidget(self.snapshot_label)
        layout.addWidget(self.snapshot_warn)
        # timer to refresh minute-snapshot info
        self._snapshot_timer = QtCore.QTimer(self)
        self._snapshot_timer.setInterval(30_000)
        self._snapshot_timer.timeout.connect(self.update_minute_snapshot_info)
        self._snapshot_timer.start()

        # load assigned MA
        self.assigned_store = AssignedMAStore()
        self.load_assigned()

        # IB worker for live positions (started/stopped by settings)
        self.ib_worker = IBWorker()
        self.ib_worker.positions_updated.connect(self.on_positions_update)
        # cache of latest signals per ticker: {ticker: {"decision": str, "ts": str}}
        self.latest_signals = {}

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
                            ts = j.get("ts")
                            # keep latest by ts (string compare ISO)
                            prev = latest.get(t)
                            if prev is None or (ts and prev.get("ts") and ts > prev.get("ts")):
                                latest[t] = {"ts": ts, "close": j.get("close"), "decision": j.get("decision")}
                        except Exception:
                            continue
        except Exception:
            latest = {}
        for r_i, row in enumerate(rows):
            ticker = row.get("ticker") or ""
            ma_type = row.get("type") or "SMA"
            length = row.get("length") or "20"
            timeframe = row.get("timeframe") or "1H"
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
            ma_type_widget.addItems(["SMA", "EMA"])
            ma_type_widget.setCurrentText(ma_type)
            self.table.setCellWidget(r_i, 3, ma_type_widget)

            length_widget = QtWidgets.QSpinBox()
            length_widget.setRange(1, 500)
            try:
                length_widget.setValue(int(length))
            except Exception:
                length_widget.setValue(20)
            self.table.setCellWidget(r_i, 4, length_widget)

            timeframe_widget = QtWidgets.QComboBox()
            timeframe_widget.addItems(["30m", "1H", "1D"])
            timeframe_widget.setCurrentText(timeframe)
            self.table.setCellWidget(r_i, 5, timeframe_widget)

            strategy_widget = QtWidgets.QComboBox()
            strategy_widget.addItems(["Market", "Market+StopLow"])
            self.table.setCellWidget(r_i, 6, strategy_widget)
            # connect change signals to save handler
            ma_type_widget.currentTextChanged.connect(lambda _t, row=r_i: self._on_cell_changed(row))
            length_widget.valueChanged.connect(lambda _v, row=r_i: self._on_cell_changed(row))
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
            # read last non-empty line
            last = None
            with snap_path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    last = ln
            if not last:
                self.snapshot_label.setText("Last snapshot: <none>")
                self.snapshot_warn.setText("")
                return
            obj = json.loads(last)
            end_ts = obj.get("end_ts") or obj.get("start_ts") or ""
            rows = obj.get("rows") or []
            # format end_ts for display: HH:MM:SS YYYY-MM-DD
            try:
                dt = datetime.fromisoformat(end_ts)
                formatted = dt.strftime("%H:%M:%S %Y-%m-%d")
            except Exception:
                formatted = end_ts or "<unknown>"
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
                rows.append({
                    "ticker": ticker,
                    "type": ma_type_w.currentText() if ma_type_w else "SMA",
                    "length": str(length_w.value() if length_w else 20),
                    "timeframe": timeframe_w.currentText() if timeframe_w else "1H",
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
            # collect unique tickers and timestamps (group by second); filter duplicates and nightly hours
            tickers = {}
            times = {}  # mapping ts_sec -> datetime
            decisions = {}  # mapping ts_sec -> {ticker: decision}
            seen_raw = set()
            for ln in recent:
                # skip exact duplicate lines
                if ln in seen_raw:
                    continue
                seen_raw.add(ln)
                try:
                    j = json.loads(ln)
                    ticker = (j.get("ticker") or j.get("symbol") or "").strip()
                    ts_raw = j.get("ts") or j.get("time") or ""
                    decision = j.get("decision") or ""
                    if not ticker or not ts_raw:
                        continue
                    # parse timestamp; group by second and filter by hour 04..20 inclusive
                    try:
                        dt = datetime.fromisoformat(ts_raw)
                    except Exception:
                        # skip unparsable timestamps
                        continue
                    hr = dt.hour
                    if hr < 4 or hr > 20:
                        continue
                    dt_sec = dt.replace(microsecond=0)
                    ts_sec = dt_sec.isoformat()

                    # preserve ticker and second-key ordering
                    tickers[ticker] = True
                    times[ts_sec] = dt_sec

                    # merge decisions: SellSignal supersedes NoSignal
                    bucket = decisions.setdefault(ts_sec, {})
                    prev = bucket.get(ticker)
                    if prev == "SellSignal":
                        # keep existing sell
                        pass
                    else:
                        if str(decision).strip().lower() == "sellsignal":
                            bucket[ticker] = "SellSignal"
                        else:
                            bucket.setdefault(ticker, "NoSignal")
                except Exception:
                    continue

            if not tickers or not times:
                return

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
                # keep only tickers present in pos_set (match full or symbol-only)
                tickers_list = [t for t in tickers_list if (t in pos_set) or (t.split(":")[-1] in pos_set)]
            except Exception:
                # if snapshot read fails, fall back to using all tickers
                pass

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
                    # format without milliseconds per requirement: YYYY-MM-DD HH:MM:SS
                    formatted_ts = f"{date_only} {dt.strftime('%H:%M:%S')}"
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


class SettingsWidget(QtWidgets.QWidget):
    connection_toggled = QtCore.Signal(bool)

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
        self.allow_auto_send.setChecked(False)
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.status_indicator = QtWidgets.QLabel("●")
        self.status_indicator.setStyleSheet("color: gray; font-size: 18px;")

        layout.addRow("Host", self.host)
        layout.addRow("Port", self.port)
        layout.addRow("Client ID", self.client_id)
        # connect button remains in settings; the Live checkbox and status light are shown in the top-right corner
        layout.addRow(self.connect_btn)
        layout.addRow(self.allow_auto_send)

        self.connect_btn.clicked.connect(self._on_connect_clicked)

    def _on_connect_clicked(self):
        # emit connect request so the main application can handle connect
        # (connect button requests connection; status light can be used to disconnect)
        self.connection_toggled.emit(True)


