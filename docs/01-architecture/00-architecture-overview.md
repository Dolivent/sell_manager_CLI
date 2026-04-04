# Architecture Overview

> **Version:** 1.2 | **Status:** Current | **Last Updated:** 2026-04-04 (S013)

---

## 1. System Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                          │
│    ┌──────────────────────┐      ┌──────────────────────────────┐   │
│    │ CLI (__main__ + cli_prompts + cli_loop) │  GUI (main_window / widgets) │   │
│    └──────────┬───────────┘      └──────────────┬───────────────┘   │
│               │                                      │                │
│    ┌──────────▼───────────────────────────────────▼──────────────┐   │
│    │                    Pipeline (pipeline.py)                  │   │
│    │   - Minute-aligned scheduling (NY timezone)                │   │
│    │   - Live position sync + assignment sync                    │   │
│    │   - Signal evaluation at top-of-hour and 15:59 NY        │   │
│    └──────────┬─────────────────────┬───────────────────────────┘   │
│               │                     │                                │
│    ┌──────────▼──────────┐ ┌──────▼───────────────────────────┐   │
│    │ minute_snapshot.py   │ │  signal_generator.py              │   │
│    │  - Downloads bars    │ │  - Reads snapshot rows           │   │
│    │  - Computes MA val   │ │  - Applies decision rule         │   │
│    │  - Logs snapshot     │ │  - Appends to signals.jsonl      │   │
│    └──────────┬───────────┘ └──────┬───────────────────────────┘   │
│               │                     │                                │
│    ┌──────────▼─────────────────────▼────────────────────────────┐   │
│    │                    Data Layer                              │   │
│    │  cache.py         - NDJSON disk cache (EXCH:SYM:gran)     │   │
│    │  aggregation.py   - 30m → 1h bar aggregation              │   │
│    │  downloader.py    - IB historical data requests            │   │
│    │  assign.py        - CSV assignments (assigned_ma.csv)       │   │
│    └──────────┬────────────────────────────────────────────────┘   │
│               │                                                     │
│    ┌──────────▼────────────────────────────────────────────────┐   │
│    │                    IB Communication Layer                   │   │
│    │  brokers/ibkr.py - IBKR adapter (ib_insync)                  │   │
│    │  ib_client.py   - alias shim → IBKRBroker                   │   │
│    │  ib_worker.py   - Qt QObject worker (GUI thread)           │   │
│    └──────────┬────────────────────────────────────────────────┘   │
│               │                                                     │
│    ┌──────────▼────────────────────────────────────────────────┐   │
│    │                    Order Execution Layer                   │   │
│    │  orders.py          - Order preparation + dry-run safety   │   │
│    │  order_manager.py   - Place → wait-fill → cancel → verify  │   │
│    │  cli_executor.py    - CLI live SellSignal transmit path     │   │
│    │  intent_store.py    - Idempotency via SHA256 keys          │   │
│    └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Data Flows

### 2a. Minute Snapshot Flow (every minute, top-of-minute)

```
IBGateway/TWS
    │
    ├─► ib_client.positions()          → enrich snapshot with live qty/price
    │
    ├─► sync_assignments_to_positions() → update assigned_ma.csv
    │
    ├─► batch_download_daily()         → 2D daily bars for daily-assigned tickers
    │
    ├─► download_halfhours()           → 30m bars for hourly-assigned tickers
    │
    ├─► aggregate_halfhours_to_hours() → 1h bars from 30m
    │
    ├─► merge_bars()                  → persist to NDJSON cache
    │
    ├─► compute SMA/EMA                → from closes list (daily or hourly)
    │
    └─► Append to logs/minute_snapshot.jsonl
```

### 2b. Signal Evaluation Flow (top-of-hour + 15:59 NY)

```
minute_snapshot.jsonl  ─► signal_generator.generate_signals_from_rows()
                                     │
                                     ├── close < MA AND abv_be == True  →  SellSignal
                                     ├── close >= MA                    →  NoSignal
                                     └── missing data                   →  Skip
                                     │
                                     └─► signals.jsonl (append)
```

### 2c. Order Execution Flow (live mode, user confirmed)

```
SellSignal entry
    │
    ├─► SHA256 intent_id = hash(ticker:bucket_ts:decision)
    │
    ├─► intent_store.exists()  ─► already attempted? → skip
    │
    ├─► intent_store.write_intent()  → status: attempting
    │
    ├─► order_manager.place_and_finalize()
    │         │
    │         ├─► ib_client.place_order()          → transmit
    │         │
    │         ├─► Wait up to 15s for fill
    │         │
    │         ├─► If filled: cancel outstanding → verify positions
    │         │
    │         └─► If timeout/cancelled: snapshot final state
    │
    └─► intent_store.update_intent()  → status: filled / cancelled / error
```

---

## 3. Module Responsibilities

### Core (`src/sellmanagement/`)

| Module | Responsibility |
|--------|---------------|
| `__main__.py` | CLI entry point; orchestrates connect → download → minute loop |
| `config.py` | Dataclass for host/port/batch settings |
| `assign.py` | Read/write `assigned_ma.csv`; sync tickers to live positions |
| `aggregation.py` | 30m → 1h bar aggregation |
| `cache.py` | NDJSON disk cache read/write/merge |
| `downloader.py` | Batch daily download; sequential 30m backfill per ticker |
| `indicators.py` | SMA, EMA computation; series enrichment |
| `ib_client.py` | ib_insync wrapper; connect/disconnect/download/positions/orders |
| `intent_store.py` | Append-only JSONL idempotency store |
| `minute_snapshot.py` | Orchestrates one snapshot cycle; writes `minute_snapshot.jsonl` |
| `order_manager.py` | Order lifecycle: place → wait → cancel → verify |
| `orders.py` | Dry-run safe order preparation and execution |
| `positions.py` | Parse `positions.txt`; ownership interval queries |
| `signal_generator.py` | Decision engine; reads snapshot, writes `signals.jsonl` |
| `signals.py` | Decision logic; structured signal logging |
| `trace.py` | Append-only trace events to `logs/ibkr_download_trace.log` |
| `updater.py` | Background thread minute scheduler skeleton |

### GUI (`src/sellmanagement/gui/`)

| Module | Responsibility |
|--------|---------------|
| `run_gui.py` | Qt application entry point |
| `main_window.py` | Main window; tabs, status light, trace tailing, pipeline wiring |
| `widgets.py` | PositionsWidget, SignalsWidget, SettingsWidget |
| `assigned_ma.py` | AssignedMAStore — CSV read/write |
| `assignment_dialog.py` | Non-blocking MA assignment dialog |
| `ib_worker.py` | Qt QObject worker; dedicated IB thread; reconnect/backoff |
| `pipeline.py` | PipelineRunner — Qt signal-driven snapshot scheduler |
| `runtime_files.py` | First-run setup for dirs and initial files |
| `settings_store.py` | Qt QSettings persistence |

---

## 4. Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `config/assigned_ma.csv` | CSV | ticker, type (SMA/EMA), length, timeframe (1H/1D) |
| `config/positions.txt` | Text | Historical position records (manual log) |
| `logs/signals.jsonl` | JSONL | Audit log — every signal decision |
| `logs/minute_snapshot.jsonl` | JSONL | Audit log — every snapshot cycle |
| `logs/ibkr_download_trace.log` | JSONL | Trace events (download, sync, errors) |
| `logs/intents.jsonl` | JSONL | Order intent idempotency records |
| `config/cache/*.ndjson` | NDJSON | Cached bar data keyed by `EXCH:SYM:gran` |

---

## 5. Concurrency Model

| Context | Mechanism |
|---------|-----------|
| CLI minute loop | `time.sleep` in main thread; wall-clock alignment to minute boundary |
| CLI IB calls | Sequential batches; brief sleep between batches |
| GUI IB thread | Dedicated `threading.Thread` with `queue.Queue` for serialised IB calls |
| GUI pipeline | `QtCore.QTimer` aligned to minute boundary; runs snapshot on IB thread |
| GUI reconnect | Exponential backoff (1s → 60s) with `threading.Timer` |
| Sleep/wake detection | `last_wake` tracking; "woke_late" trace event when gap > 1.5× interval |
