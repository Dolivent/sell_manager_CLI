# Reference Documentation — Index

> **Purpose:** Canonical technical reference for all config formats, module APIs, and runbook procedures.  
> **Rule:** When a config format or API changes, update the relevant reference doc in the same commit.

---

## Files

| # | File | Contents |
|---|-------|---------|
| 01 | [`01-config-files.md`](01-config-files.md) | File formats for all config, cache, and log files |
| 02 | [`02-module-api.md`](02-module-api.md) | Public API of every module |
| 03 | [`03-runbook.md`](03-runbook.md) | Operational procedures: startup, shutdown, recovery |

---

## Quick Reference

### IB Connection Ports

| Port | Use |
|------|-----|
| `4001` | IB Gateway (SSL) — **default** |
| `7496` | TWS (non-SSL) |
| `7497` | TWS (paper trading) |

### Cache Key Format

```
EXCHANGE:SYMBOL:GRANULARITY
Examples:  NASDAQ:AAPL:1d  ,  NYSE:IBM:1h  ,  SMART:SPY:30m
```

### MA Lengths Available

```
SMA/EMA: 5, 10, 20, 50, 100, 150, 200
```

### Timeframe Values

| Value | Meaning |
|-------|---------|
| `1H` | Hourly evaluation (checked at top of every hour + 15:59 NY) |
| `D` / `1D` | Daily evaluation (checked at 15:59 NY only) |

### Signal Decision Conditions

A `SellSignal` is generated when **all** of the following are true:
1. `last_close < ma_value` (price crossed below the assigned MA)
2. `abv_be == True` (both `close > avgCost` AND `ma > avgCost`)

### Audit Log Locations

| Log | File | Format |
|-----|------|--------|
| Signal decisions | `logs/signals.jsonl` | JSONL |
| Minute snapshots | `logs/minute_snapshot.jsonl` | JSONL |
| Trace events | `logs/ibkr_download_trace.log` | JSONL (rotating; default 10 MB × 5; see runbook §2a.1 for env overrides) |
| Order intents | `logs/intents.jsonl` | JSONL |

### GUI smoke test

See [`../06-user-guide/02-gui-smoke.md`](../06-user-guide/02-gui-smoke.md).
