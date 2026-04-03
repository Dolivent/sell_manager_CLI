# T003 — Extract Snapshot Logic from `minute_snapshot.py`

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T003 |
| Title | Extract snapshot logic from `minute_snapshot.py` |
| Status | OPEN |
| Priority | P1 |
| Created | 2026-04-04 |
| Session | S001 |
| Detail File | `docs/03-tasks/tracker/T003-extract-snapshot-logic.md` |

---

## 1. Goal

Break `run_minute_snapshot()` in `minute_snapshot.py` (approx. 400 lines) into focused sub-functions with clear responsibilities, a defined data structure for intermediate state, and unit tests for each sub-function.

---

## 2. Background

`run_minute_snapshot` handles all of the following in one large function:

1. Fetch live positions and open orders from IB
2. Build position maps (avg cost, qty, stop prices)
3. Partition tickers by assigned timeframe (daily vs hourly)
4. Download daily bars for daily-assigned tickers
5. Download 30m bars for hourly-assigned tickers
6. Merge bars into cache
7. Aggregate 30m → 1h
8. Load bars from cache
9. Freshness detection and stale backfill
10. MA computation (SMA/EMA per assignment)
11. Build snapshot rows with abv_be calculation
12. Write to `logs/minute_snapshot.jsonl`
13. Return (end_ts, rows)

This makes the function:
- Extremely difficult to test in isolation
- Hard to debug — a single breakpoint covers too much
- Risky to modify — changing one concern can accidentally affect another

---

## 3. Proposed Structure

```python
@dataclass
class SnapshotRow:
    ticker: str
    assigned_type: str
    assigned_length: int
    assigned_timeframe: str
    ma_value: Optional[float]
    last_close: Optional[float]
    distance_pct: Optional[float]
    position: float
    avg_cost: Optional[float]
    abv_be: bool

@dataclass
class SnapshotContext:
    ib_client: IBClient
    tickers: list[str]
    assignments: dict  # from get_assignments_list()
    live_positions: list
    open_orders: list
    start_ts: str
    snap_dt: datetime

def run_minute_snapshot(ib_client, tickers, concurrency=32) -> (str, list[SnapshotRow]):
    ctx = _build_context(ib_client, tickers)
    _fetch_and_cache(ctx)
    _handle_stale_bars(ctx)
    rows = _compute_snapshot_rows(ctx)
    _write_snapshot_log(ctx.end_ts, rows)
    return ctx.end_ts, rows

def _build_context(ib_client, tickers) -> SnapshotContext: ...
def _fetch_and_cache(ctx) -> None: ...
def _handle_stale_bars(ctx) -> None: ...
def _compute_snapshot_rows(ctx) -> list[SnapshotRow]: ...
def _write_snapshot_log(end_ts: str, rows: list[SnapshotRow]) -> None: ...
```

---

## 4. Acceptance Criteria

- [ ] `run_minute_snapshot` is under 30 lines of orchestration code
- [ ] Each sub-function has a clear single responsibility
- [ ] `SnapshotContext` dataclass carries all intermediate state
- [ ] Each sub-function has unit tests
- [ ] The `minute_snapshot.py` file is under 200 lines total
- [ ] `docs/05-reference/02-module-api.md` is updated to document new sub-functions
