# Module API Reference

> **Version:** 1.7 | **Last Updated:** 2026-04-04 (S013)  
> Covers public-facing functions and classes only. Internal helpers are omitted.

---

## Core Modules (`src/sellmanagement/`)

---

### `brokers/` package

```python
# brokers/__init__.py
def create_broker(name: str = "ibkr", **kwargs) -> IBKRBroker:
    """Return a broker adapter. Raises ValueError for unknown ``name``."""

# brokers/ibkr.py
class IBKRBroker:
    """Interactive Brokers session via ``ib_insync`` (connect, historical bars, orders)."""
```

`ib_client.IBClient` is an alias of `IBKRBroker` for backward compatibility.

---

### `config.py`

```python
@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 1
    dry_run: bool = True
    download_workers: int = 2
    download_concurrency: int = 4
    batch_size: int = 32
    batch_delay: float = 6.0
```

---

### `assign.py`

```python
def set_assignment(ticker: str, ma_type: str, length: int, timeframe: str = "1H") -> None:
    """Append or update assignment in config/assigned_ma.csv.
    Raises ValueError if type is not SMA/EMA or length <= 0."""

def get_assignments() -> dict:
    """Returns {TICKER_UPPER: {type, length, timeframe}}.
    Returns {} if file missing."""

def get_assignments_list() -> list:
    """Returns [{ticker, type, length, timeframe}, ...] in file order."""

def sync_assignments(tokens: Iterable[str], default_type="SMA", default_length=50, default_timeframe="1H") -> dict:
    """Sync CSV to exactly tokens list.
    Returns {added: [...], removed: [...], kept: [...]}."""

def sync_assignments_to_positions(tokens: Iterable[str]) -> dict:
    """Sync CSV to live positions. New tickers get blank assignment fields.
    Returns {added: [...], removed: [...], kept: [...]}."""

def export_assignments_json(dest: str | Path) -> None:
    """Write ``{version, assignments}`` JSON preset from current CSV."""

def import_assignments_json(path: str | Path, *, merge: bool = False) -> dict:
    """Load preset JSON; replace CSV or merge (upsert) by ticker. Returns {mode, count}."""
```

---

### `indicators.py`

```python
def simple_moving_average(values: List[float], length: int) -> Optional[float]
def exponential_moving_average(values: List[float], length: int) -> Optional[float]
def series_sma(values: List[float], length: int) -> List[Optional[float]]
def series_ema(values: List[float], length: int) -> List[Optional[float]]
def compute_sma_series_all(values: List[float], lengths: List[int]) -> Dict[int, List[Optional[float]]]
def compute_ema_series_all(values: List[float], lengths: List[int]) -> Dict[int, List[Optional[float]]]
def enrich_ndjson_with_indicators(
    input_path: str,
    output_path: Optional[str] = None,
    sma_lengths: List[int] = (5, 10, 20, 50, 100, 150, 200),
    ema_lengths: List[int] = (5, 10, 20, 50, 100, 150, 200),
    overwrite: bool = False,
) -> str:
    """Read NDJSON of OHLCV bars, add SMA_n/EMA_n columns, write enriched NDJSON. Returns output path."""
```

---

### `cache.py`

```python
CACHE_DIR = Path("config/cache")  # resolved from project root

def persist_bars(key: str, bars: Iterable[dict]) -> None:
    """Append bars to cache file (append-only)."""

def load_bars(key: str, limit: int | None = None) -> List[Any]:
    """Load bars from cache. Returns newest-last. If limit set, return last `limit` rows."""

def write_bars(key: str, bars: Iterable[dict]) -> None:
    """Overwrite cache file with provided bars (replace-all)."""

def merge_bars(key: str, new_bars: Iterable[dict]) -> None:
    """Merge new_bars into existing cache by Date. Dedupe by timestamp. Sort ascending."""
```

---

### `aggregation.py`

```python
def aggregate_halfhours_to_hours(halfhours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate 30-minute bars (newest-last) into hourly bars.
    Returns hourly bars in newest-last order."""
```

---

### `downloader.py`

```python
def batch_download_daily(ib_client, tickers: Iterable[str], batch_size=32, batch_delay=6.0, duration="1 Y") -> Dict[str, List[dict]]:
    """Download daily bars in batches. Returns {ticker: rows}. Rows may be empty on failure."""

def persist_batch_halfhours(ib_client, tickers: Iterable[str], batch_size=8, batch_delay=6.0, target_hours=200) -> Dict[str, int]:
    """For each ticker: backfill 30m bars, persist to 30m cache, aggregate to 1h, persist to 1h cache.
    Returns {ticker: bars_persisted_count}."""

def backfill_halfhours_sequential(ib_client, token: str, target_bars=200) -> List[dict]:
    """Public wrapper: backfill until at least `target_bars` 30m bars for one ticker.
    Returns list of bar dicts (newest-last)."""
```

---

### `dashboard.py`

```python
def read_latest_snapshot_record(snapshot_path: Path) -> Optional[Dict[str, Any]]:
    """Last JSON object in an NDJSON minute-snapshot file."""

def dashboard_port() -> int:
    """From SELLMANAGEMENT_DASHBOARD_PORT or default 5055."""

def create_app(*, snapshot_path: Path | None = None, signals_path: Path | None = None) -> Flask:
    """Flask app with route ``/`` — latest snapshot rows + latest signal batch."""

def run_dashboard(*, host: str = "127.0.0.1") -> None:
    """``app.run`` on dashboard_port(); logs listen URL."""
```

---

### `alerts.py`

```python
def send_smtp_alert(subject: str, body: str) -> bool:
    """Send plain-text email if env is complete; else log one WARNING per process and return False.

    Env: SELLMANAGEMENT_SMTP_HOST, SELLMANAGEMENT_ALERT_TO, optional SELLMANAGEMENT_SMTP_PORT (default 587),
    optional SELLMANAGEMENT_SMTP_USER + SELLMANAGEMENT_SMTP_PASS (if user set, pass key must exist)."""

def alert_sellsignal_logged(entry: Dict[str, Any]) -> None:
    """Best-effort email after a SellSignal is logged."""

def order_transmit_needs_alert(res: Dict[str, Any]) -> bool:
    """True if live result status should trigger a failure email."""

def alert_order_failed(*, ticker: Optional[str], result: Dict[str, Any]) -> None
def alert_order_exception(*, ticker: Optional[str], error: str) -> None
```

---

### `signals.py`

```python
def _log_path() -> Path:  # "logs/signals.jsonl"

def now_iso() -> str:  # UTC ISO timestamp

def decide(close: float, ma_type: str, length: int, values: List[float]) -> Dict[str, Any]:
    """Returns {decision, reason, ma_value, close}.
    decision is 'SellSignal' | 'NoSignal' | 'Skip'."""

def append_signal(entry: Dict[str, Any]) -> bool:
    """Append entry to signals.jsonl. Returns True on success.
    After a successful write, if decision is SellSignal, may send SMTP alert (see alerts.py)."""
```

---

### `signal_generator.py`

```python
def _snapshot_path() -> Path:  # "logs/minute_snapshot.jsonl"

def read_latest_minute_snapshot() -> List[Dict[str, Any]]:
    """Returns rows array from last minute_snapshot entry. [] if missing."""

def generate_signals_from_rows(
    rows: List[Dict[str, Any]],
    evaluate_hourly: bool = True,
    evaluate_daily: bool = False,
    dry_run: bool = True,
) -> List[Dict[str, Any]]:
    """Evaluate signal decisions for snapshot rows.
    Returns list of appended signal entries."""

def generate_signals_from_latest_snapshot(
    evaluate_hourly: bool = True,
    evaluate_daily: bool = False,
    dry_run: bool = True,
) -> List[Dict[str, Any]]:
    """Convenience: read latest snapshot then call generate_signals_from_rows."""
```

---

### `orders.py`

```python
@dataclass
class PreparedOrder:
    symbol: str
    quantity: int
    order_type: str  # "MKT" or "LMT"
    details: Dict[str, Any]

def prepare_close_order(symbol: str, quantity: int, order_type: str = "MKT") -> PreparedOrder:

def execute_order(ib_client: Any, prepared: PreparedOrder, dry_run: bool = True) -> Dict[str, Any]:
    """Execute or simulate an order. Returns {status, ...}."""
```

---

### `order_manager.py`

```python
def find_orders_for_symbol(open_orders: List[Any], symbol: str) -> List[Any]:
    """Filter open orders by symbol/exchange token."""

def place_and_finalize(ib_client, prepared_order: Dict[str, Any], timeout: int = DEFAULT_FILL_TIMEOUT, dry_run: bool = False) -> Dict[str, Any]:
    """Place an order, wait for fill/cancel/timeout, cancel outstanding, verify.
    When dry_run=True, returns simulated result without placing live order.
    Returns {status, placed_trade, cancelled, positions_before, positions_after, ..., dry_run}."""
```

---

### `cli_prompts.py`

```python
MaOption = Tuple[str, int, str]  # ("SMA"|"EMA", length, "1H"|"D")

def build_ma_assignment_options(lengths=..., timeframes=...) -> List[MaOption]:
def default_ma_selection_index(options, default=("SMA", 50, "1H")) -> int  # 1-based
def print_ma_assignment_menu(options, default_idx: int) -> None
def read_ma_selection(options, default_idx: int, *, reader: Callable[[str], str] | None = None) -> MaOption
def prompt_ma_assignment(ticker: str, *, options=..., reader=...) -> MaOption:
    """Interactive MA type/length/timeframe; ``reader`` overrides ``input`` for tests."""

def confirm_live_transmit(*, assume_yes: bool = False, reader=...) -> bool:
    """True if user types YES exactly, or ``assume_yes`` (e.g. CLI ``--yes-to-all``)."""
```

---

### `cli_executor.py`

```python
def transmit_live_sell_signals(ib: Any, generated: List[Dict[str, Any]], *, snapshot_ts: str) -> None:
    """Live path only: place MKT closes for SellSignal rows (intent dedup, qty cap, execute_order).
    On failure statuses or exceptions, may send SMTP alert (see alerts.py)."""
```

---

### `trace.py`

```python
def _trace_rotation_settings() -> tuple[int, int]:
    """Return (maxBytes, backupCount) for the trace RotatingFileHandler.

    Env: SELLMANAGEMENT_TRACE_MAX_MB (decimal MB = 1e6 bytes per unit, default 10),
    SELLMANAGEMENT_TRACE_BACKUPS (default 5). Invalid values use defaults; results clamped.
    """

def append_trace(record: dict) -> None:
    """Append one JSON object per line to logs/ibkr_download_trace.log via RotatingFileHandler.

    Rotation uses _trace_rotation_settings() (defaults 10 MB, 5 backups).
    """
```

---

### `log_config.py`

```python
def setup_logging(console_level: int = logging.WARNING) -> None:
    """Attach stderr StreamHandler to the ``sellmanagement`` logger (idempotent). CLI + GUI call this at startup."""
```

---

### `cli_loop.py`

```python
def read_last_signal_batch(log_path: Path) -> List[Dict[str, Any]]
def print_last_signals_preview(log_path: Path) -> None
def sleep_until_next_minute_ny(*, max_chunk_seconds: float = 5.0, time_sleep=...) -> None
def heartbeat_cycle(last_wake, append_trace, *, heartbeat_interval: float = 60.0, now_fn: Callable[[], datetime] | None = None) -> datetime
def sort_snapshot_rows_for_display(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]
def print_snapshot_table(rows: List[Dict[str, Any]]) -> None
```

---

### `intent_store.py`

```python
def _store_path() -> Path:  # "logs/intents.jsonl"

def write_intent(intent: Dict[str, Any]) -> None:  # append to intents.jsonl

def exists(intent_id: str) -> bool:  # True if intent already in store

def update_intent(intent_id: str, updates: Dict[str, Any]) -> None:  # append update record

def read_recent(limit: int = 200) -> list[Dict[str, Any]]:
```

---

### `positions.py`

```python
def parse_positions_text(text: str) -> Dict[str, List[Interval]]:
    """Parse positions.txt. Returns {TICKER: [(entry_dt, exit_dt_or_None), ...]}."""

def parse_positions_file(path: str | Path = "config/positions.txt") -> Dict[str, List[Interval]]:
    """Convenience: read and parse positions.txt."""

def is_in_position_at(ticker: str, dt: datetime, positions_map: Dict[str, List[Interval]]) -> bool:
    """Return True if ticker is in a position at datetime dt."""
```

---

### `minute_snapshot.py`

```python
LOG_PATH = Path("logs/minute_snapshot.jsonl")

@dataclass
class SnapshotRow:
    ticker: str
    assigned_type: Optional[str]
    assigned_length: Optional[int]
    assigned_timeframe: Optional[str]
    ma_value: Optional[float]
    last_close: Optional[float]
    distance_pct: Optional[float]
    position: float
    avg_cost: Optional[float]
    abv_be: bool
    ts: str
    last_bar_date: Optional[str]
    assigned_ma: Optional[str]
    def to_dict(self) -> Dict[str, Any]: ...

@dataclass
class SnapshotContext:
    ib_client: Any
    tickers: List[str]
    assignments: Dict[str, Dict[str, Any]]
    live_positions_raw: List[Any]
    open_orders_raw: List[Any]
    pos_avg_map: Dict[str, Optional[float]]
    pos_size_map: Dict[str, float]
    orders_map: Dict[str, List[float]]
    daily_tickers: List[str]
    hourly_tickers: List[str]
    daily_results: Dict[str, List[Dict[str, Any]]]
    start_ts: str
    snap_dt: Optional[datetime]

def run_minute_snapshot(ib_client, tickers: List[str], concurrency: int = 32) -> (str, List[Dict[str, Any]]):
    """Run one snapshot cycle. Returns (end_ts: str, rows: List[Dict]).
    Rows contain per-ticker MA values and snapshot data. Writes to LOG_PATH.
    Internal phases: _build_context, _fetch_and_cache, _compute_snapshot_rows, _write_snapshot_log."""
```

---

### `ib_client.py`

Shim: ``IBClient`` is an alias of ``brokers.ibkr.IBKRBroker``.

```python
class IBClient:  # same as IBKRBroker
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1, use_rth: bool = True)
    def connect(self, timeout: int = 10) -> bool
    def disconnect(self) -> None
    def download_daily(self, token: str, duration: str = "1 Y") -> List[Dict[str, Any]]
    def download_halfhours(self, token: str, duration: str = "31 D", end: str | None = None) -> List[Dict[str, Any]]
    def positions(self) -> List[Any]  # ib_insync Position objects
    def openOrders(self) -> List[Any]
    def prepare_order(self, token: str, quantity: int, order_type: str = "MKT", **kwargs) -> Dict[str, Any]
    def place_order(self, prepared_or_token, quantity: int | None = None, order_type: str | None = None, transmit: bool = True, **kwargs) -> Dict[str, Any]
    def cancel_order(self, order_or_trade) -> Dict[str, Any]
    def get_trade_status(self, trade) -> str  # 'filled' | 'cancelled' | 'done' | 'pending' | 'unknown'
```

### `utils/ticker.py`

```python
def normalise_ticker(ticker: str) -> str:
    """Return canonical normalised form of a ticker string (uppercase, stripped).
    Examples: "aapl" -> "AAPL", "NASDAQ:AAPL" -> "NASDAQ:AAPL", "" -> ""."""

def ticker_to_symbol(ticker: str) -> str:
    """Extract bare symbol from a ticker token, stripping exchange prefix.
    Examples: "NASDAQ:AAPL" -> "AAPL", "AAPL" -> "AAPL"."""

def tickers_match(a: str, b: str) -> bool:
    """Return True if two ticker strings refer to the same instrument.
    Matches on exact normalised equality or bare-symbol equality."""

---

## GUI Modules (`src/sellmanagement/gui/`)

---

### `run_gui.py`

```python
def main() -> int:
    """Create Qt app, show MainWindow, return app.exec_() exit code."""
```

---

### `main_window.py`

```python
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None)
    # Signals
    # Internal slots: _on_ib_connected, _on_status_clicked, _on_pipeline_need_assign, _append_log, _poll_trace
```

---

### `widgets.py`

```python
class ClientIdSelector(QtWidgets.QSpinBox):
    """IB API client id spin box (range 1–999999)."""

class PositionsWidget(QtWidgets.QWidget):
    def load_assigned(self)  # Load assigned_ma.csv into table
    def update_minute_snapshot_info(self)  # Read latest snapshot, update info label
    def on_positions_update(self, positions: list)  # Handle live position updates from ib_worker
    def on_signals_updated(self, latest_map: dict)  # Handle signal updates from SignalsWidget
    def set_show_premarket(self, val: bool)  # Toggle pre/post-market signal display
    # Slots: _on_cell_changed

class SignalsWidget(QtWidgets.QWidget):
    signals_updated = QtCore.Signal(object)  # Emitted with latest per-ticker decisions
    def set_show_premarket(self, val: bool)
    # Internal: _poll_signals (timer-driven)
```

---

### `assigned_ma.py`

```python
class AssignedMAStore:
    def __init__(self, path: Path | None = None)
    def iter_rows(self) -> Iterator[Dict[str, str]]  # Iterate CSV rows
    def write_rows(self, rows: list) -> None  # Atomic write
```

---

### `assignment_dialog.py`

```python
class AssignmentDialog(QDialog):
    def __init__(self, tickers: List[str], parent=None)
    def assignments(self) -> Dict[str, Tuple[str, int, str]]  # {ticker: (type, length, timeframe)}
    def show_non_blocking(self, accept_callback=None, reject_callback=None) -> None:
        """Show dialog non-modally, call callbacks on accept/reject."""
```

---

### `ib_worker.py`

```python
class IBWorker(QObject):
    connected = QtCore.Signal(bool)
    positions_updated = QtCore.Signal(list)

    def __init__(self, parent=None)
    def connect(self, host="127.0.0.1", port=4001, client_id=1, use_rth=True) -> None
    def disconnect(self) -> None
    def shutdown(self, timeout: float = 2.0) -> None
    def run_on_thread(self, fn, timeout: float | None = None)  # Run callable on IB thread, return result
    def _schedule_reconnect(self, host=None, port=None, client_id=None, use_rth=None) -> None  # Schedule reconnect on background thread (avoids queue re-entry)
```

---

### `pipeline.py`

```python
class PipelineRunner(QObject):
    started = QtCore.Signal()
    stopped = QtCore.Signal()
    snapshot_done = QtCore.Signal(object)   # emits (end_ts, rows)
    need_assign = QtCore.Signal(list)       # emits [ticker, ...] needing assignment

    def __init__(self, ib_worker, parent=None)
    def start(self) -> None
    def stop(self) -> None
    def run_snapshot_once(self) -> (str, list)  # Returns (end_ts, rows)
    def confirm_assignments(self) -> None  # Called by GUI after user fills assignment dialog
```

---

### `settings_store.py`

```python
def get_bool(key: str, default: bool = False) -> bool
def set_value(key: str, value) -> None
def get_value(key: str, default=None)
def get_use_rth() -> bool  # Returns stored use_rth flag, defaults True
def set_use_rth(value: bool) -> None  # Persist use_rth flag via Qt QSettings
def get_client_id() -> int  # Stored IB client id (1–999999), default 1
def set_client_id(value: int) -> None  # Persist client id (`ib/client_id`)
```

---

### `widgets.py` — `SettingsWidget`

```python
class SettingsWidget(QtWidgets.QWidget):
    connection_toggled = QtCore.Signal(bool)
    show_premarket_toggled = QtCore.Signal(bool)
    assignments_changed = QtCore.Signal()  # after MA preset import
    use_rth_checkbox: QtWidgets.QCheckBox  # "Use regular trading hours only (RTH)"
    live_checkbox: QtWidgets.QCheckBox
    allow_auto_send: QtWidgets.QCheckBox
    show_premarket_checkbox: QtWidgets.QCheckBox
    btn_ma_export: QtWidgets.QPushButton
    btn_ma_import: QtWidgets.QPushButton
    ma_import_merge: QtWidgets.QCheckBox
    host: QtWidgets.QLineEdit
    port: QtWidgets.QSpinBox
    client_id: ClientIdSelector  # persisted via settings_store on change
    console: QtWidgets.QPlainTextEdit

    @property
    def use_rth(self) -> bool: ...  # Returns current use_rth checkbox value
```

---

### `runtime_files.py`

```python
def ensure_runtime_files(root: Path | None = None) -> Dict[str, Path]:
    """Create config/, logs/, config/cache/ dirs. Create empty assigned_ma.csv, signals.jsonl.
    Returns dict of created paths."""
```
