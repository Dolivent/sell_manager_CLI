# Config File Reference

> **Version:** 1.0 | **Last Updated:** 2026-04-04

---

## 1. `config/assigned_ma.csv`

The primary configuration file. Controls which moving average is applied to each position.

**Path:** `config/assigned_ma.csv`  
**Created by:** `assign.py::set_assignment()` or manual edit  
**Read by:** `assign.py`, `minute_snapshot.py`, `widgets.py`, `pipeline.py`

### Format

```csv
ticker,type,length,timeframe
NASDAQ:AAPL,SMA,50,1H
NYSE:IBM,EMA,200,1H
NASDAQ:MSFT,SMA,20,D
```

### Fields

| Field | Required | Values | Default |
|-------|----------|--------|---------|
| `ticker` | Yes | Exchange-prefixed token, e.g. `NASDAQ:AAPL` | — |
| `type` | Yes | `SMA` or `EMA` | — |
| `length` | Yes | Integer: `5, 10, 20, 50, 100, 150, 200` | — |
| `timeframe` | Recommended | `1H` (hourly) or `D` (daily) | `1H` |

### Notes

- Blank `type`/`length`/`timeframe` rows indicate unassigned tickers; the app will prompt for assignment at startup.
- The ticker format must match the format returned by IB. For stocks, use `EXCHANGE:SYMBOL` (e.g., `NASDAQ:AAPL`). The exchange is usually `SMART` unless a specific listing exchange is preferred.
- Changes to this file are detected by the GUI's file watcher and reload automatically.

---

## 2. `config/positions.txt`

Historical position log. Used by `positions.py` to determine ownership intervals.

**Path:** `config/positions.txt`  
**Read by:** `positions.py::parse_positions_file()`

### Format

```
TICKER long
  YYYY-MM-DD HH:MM:SS price action
  YYYY-MM-DD HH:MM:SS price action

TICKER short
  YYYY-MM-DD HH:MM:SS price action
```

### Rules

- **Header line:** `<TICKER> <direction>` where direction is `long` or `short`.
- **Event lines:** Indented, format `YYYY-MM-DD HH:MM:SS <price> <action>`.
- For `long` positions: `bought` opens the position, `sold` closes it.
- For `short` positions: `sold` opens, `bought` closes.
- Multiple `bought` entries while already open are merged into a single open interval.

---

## 3. `logs/signals.jsonl`

Append-only audit log for every signal decision.

**Path:** `logs/signals.jsonl`  
**Written by:** `signals.py::append_signal()`  
**Appended by:** `signal_generator.py::generate_signals_from_rows()`  
**Read by:** `widgets.py`, `scripts/compare_versions.py`

### Record Format

```json
{
  "ticker": "NASDAQ:AAPL",
  "decision": "SellSignal",
  "close": 182.45,
  "ma_value": 185.20,
  "assigned_timeframe": "H",
  "assigned_ma": "SMA(50)",
  "assigned_length": 50,
  "assigned_type": "SMA",
  "position": 100.0,
  "avg_cost": 175.30,
  "action": "simulate",
  "ts": "2026-04-04T15:59:00-04:00"
}
```

### Decision Values

| Value | Meaning |
|-------|---------|
| `SellSignal` | All conditions met — sell prepared |
| `NoSignal` | Close >= MA — no action |
| `Skip` | Insufficient data |

---

## 4. `logs/minute_snapshot.jsonl`

Append-only audit log for every snapshot cycle.

**Path:** `logs/minute_snapshot.jsonl`  
**Written by:** `minute_snapshot.py::run_minute_snapshot()`  
**Read by:** `signal_generator.py`, `widgets.py`

### Record Format

```json
{
  "start_ts": "2026-04-04T15:00:00-04:00",
  "end_ts": "2026-04-04T15:00:12-04:00",
  "rows": [
    {
      "ticker": "NASDAQ:AAPL",
      "assigned_type": "SMA",
      "assigned_length": 50,
      "assigned_timeframe": "H",
      "assigned_ma": "SMA(50)",
      "ma_value": 185.20,
      "last_close": 182.45,
      "distance_pct": -1.48,
      "position": 100.0,
      "avg_cost": 175.30,
      "abv_be": true
    }
  ]
}
```

---

## 5. `logs/ibkr_download_trace.log`

Append-only trace log for download, sync, and error events.

**Path:** `logs/ibkr_download_trace.log`  
**Written by:** `trace.py::append_trace()`  
**Read by:** `main_window.py` (GUI trace tailing)

### Record Format

```json
{"ts": "2026-04-04T14:35:00-04:00", "event": "heartbeat"}
{"ts": "2026-04-04T14:35:00-04:00", "event": "woke_late", "gap_seconds": 300.5, "reason": "suspiciously_large_gap"}
{"ts": "2026-04-04T14:35:01-04:00", "event": "batch_download_daily_done", "tickers": ["NASDAQ:AAPL"], "count": 2}
```

### Known Event Types

| Event | Meaning |
|-------|---------|
| `heartbeat` | Process alive at minute boundary |
| `woke_late` | Gap detected — likely resumed from sleep |
| `sync_assignments_before_snapshot` | Assignment sync result |
| `batch_download_daily_done` | Daily bar download completed |
| `halfhour_download_done` | 30m bar download completed |
| `signal_evaluation_done` | Signal generation completed |
| `order_attempt` | Order transmission attempted |
| `order_skipped` | Order skipped (no position, duplicate) |

---

## 6. `logs/intents.jsonl`

Append-only idempotency store for order intents.

**Path:** `logs/intents.jsonl`  
**Written by:** `intent_store.py`  
**Read by:** `__main__.py`

### Record Format (initial write)

```json
{
  "intent_id": "a3f8b2...",
  "ticker": "NASDAQ:AAPL",
  "decision": "SellSignal",
  "bucket_ts": "2026-04-04T15:00:00-04:00",
  "requested_qty": 100,
  "qty_to_send": 100,
  "status": "attempting",
  "ts": "2026-04-04T15:00:05-04:00"
}
```

### Record Format (update)

```json
{
  "intent_id": "a3f8b2...",
  "update": {"status": "filled", "completed_ts": "2026-04-04T15:00:18-04:00"}
}
```

---

## 7. `config/cache/*.ndjson`

Disk cache for historical bar data.

**Path:** `config/cache/<EXCH>__<SYMBOL>__<GRAN>.ndjson`  
**Example:** `config/cache/NASDAQ__AAPL__1d.ndjson`  
**Written by:** `cache.py::write_bars()`, `cache.py::merge_bars()`  
**Read by:** `minute_snapshot.py`, `cache.py::load_bars()`

### Format

One JSON object per line, newest-first.

```json
{"Date": "2026-04-04", "Open": 181.0, "High": 183.5, "Low": 180.2, "Close": 182.45, "Volume": 52000000}
{"Date": "2026-04-03", "Open": 180.0, "High": 182.0, "Low": 179.5, "Close": 181.20, "Volume": 48000000}
```

### Cache Key Mapping

| Timeframe | MA Length | Bar Type | Cache Key Suffix |
|-----------|-----------|----------|-----------------|
| `1H` | any | 30m (raw) | `30m` |
| `1H` | any | 1h (aggregated) | `1h` |
| `D` | any | 1d (daily) | `1d` |
