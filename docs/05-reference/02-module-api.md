# Module API Reference

> **Version:** 1.0 | **Last Updated:** 2026-04-04  
> Covers public-facing functions and classes only. Internal helpers are omitted.

---

## Core Modules (`src/sellmanagement/`)

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

### `signals.py`

```python
def _log_path() -> Path:  # "logs/signals.jsonl"

def now_iso() -> str:  # UTC ISO timestamp

def decide(close: float, ma_type: str, length: int, values: List[float]) -> Dict[str, Any]:
    """Returns {decision, reason, ma_value, close}.
    decision is 'SellSignal' | 'NoSignal' | 'Skip'."""

def append_signal(entry: Dict[str, Any]) -> bool:
    """Append entry to signals.jsonl. Returns True on success."""
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

```python
class IBClient:
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
    def connect(self, host="127.0.0.1", port=4001, client_id=1) -> None
    def disconnect(self) -> None
    def shutdown(self, timeout: float = 2.0) -> None
    def run_on_thread(self, fn, timeout: float | None = None)  # Run callable on IB thread, return result
    def _schedule_reconnect(self, host=None, port=None, client_id=None) -> None  # Schedule reconnect on background thread (avoids queue re-entry)
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
```

---

### `runtime_files.py`

```python
def ensure_runtime_files(root: Path | None = None) -> Dict[str, Path]:
    """Create config/, logs/, config/cache/ dirs. Create empty assigned_ma.csv, signals.jsonl.
    Returns dict of created paths."""
```
