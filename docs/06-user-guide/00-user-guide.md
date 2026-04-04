# User Guide

> **Version:** 1.1 | **Last Updated:** 2026-04-04 (S007)

---

## Related

- [GUI smoke checklist](02-gui-smoke.md) — quick manual regression after changes.

## Table of Contents

1. [What This Tool Does](#1-what-this-tool-does)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [CLI Mode](#4-cli-mode)
5. [GUI Mode](#5-gui-mode)
6. [Configuring Moving Averages](#6-configuring-moving-averages)
7. [Understanding Signals](#7-understanding-signals)
8. [Going Live](#8-going-live)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What This Tool Does

`sell_manager_CLI` monitors your Interactive Brokers positions and prepares sell orders when a position closes below its assigned moving average. It is designed to be **safe by default**:

- In dry-run mode, orders are prepared and logged but never sent.
- In live mode, an explicit `YES` confirmation is required before any order is transmitted.
- A full audit trail is kept in `logs/signals.jsonl`.

**The core rule:** When a position's latest close is strictly below its assigned moving average — and the position is above break-even — the tool prepares a full-close sell order.

---

## 2. Installation

### Requirements

- Python 3.10 or newer
- Interactive Brokers Gateway or TWS installed and running
- Recommended: IB Paper Trading account for testing

### Steps

```bash
# Clone or navigate to the project
cd sell_manager_CLI

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install the package (editable mode)
pip install -U pip
pip install -e .

# Install GUI extras (optional but recommended)
pip install ".[gui]"
```

---

## 3. Quick Start

```bash
# Start in dry-run mode (safe)
python -m sellmanagement
```

The app will:
1. Connect to IB at `127.0.0.1:4001`.
2. Fetch your current positions.
3. Download recent market data.
4. Compute your assigned moving averages.
5. Enter the minute snapshot loop — updating every minute.

---

## 4. CLI Mode

### Commands

```bash
# Start in dry-run mode
python -m sellmanagement

# Start in live mode (orders transmitted)
python -m sellmanagement --live

# Assign an MA without starting the loop
python -m sellmanagement assign NASDAQ:AAPL SMA 50 --timeframe 1H

# Launch GUI mode
python -m sellmanagement --gui
```

### Output Format

The CLI prints a table every minute:

```
ticker                  last_close    ma_value  distance_pct    assigned_ma     abv_be
NASDAQ:AAPL              182.45       185.20        -1.5%    H SMA(50)           T
NYSE:IBM                 142.10       141.50         0.4%    H EMA(200)          T
```

- **`abv_be` (Above Break-Even):** `T` means the position is profitable enough that both close AND MA are above your average cost.
- **`distance_pct`:** How far the close is above/below the MA. Negative means below MA (potential sell signal).

---

## 5. GUI Mode

### Starting the GUI

```bash
# Option 1: via module
python -m sellmanagement --gui

# Option 2: from source
python src/sellmanagement/gui/run_gui.py

# Option 3: via batch file (Windows)
run.bat
```

### GUI Tabs

| Tab | Description |
|-----|-------------|
| **Positions** | Table of all tickers with MA assignments. Shows live qty/price from IB. Status column shows signal colour. |
| **Signals** | Real-time grid of signal decisions. Red = SellSignal, Green = NoSignal. |
| **Settings** | IB host/port/client ID, Live mode toggle, pre/post-market toggle, console log. |

### Status Light

The **●** in the top-right corner is the IB connection status:
- **Green:** Connected
- **Red:** Disconnected
- **Gray:** Not started

Click it to connect or disconnect.

---

## 6. Configuring Moving Averages

### Format

Edit `config/assigned_ma.csv`:

```csv
ticker,type,length,timeframe
NASDAQ:AAPL,SMA,50,1H
NYSE:IBM,EMA,200,1H
NASDAQ:MSFT,SMA,20,D
```

| Field | Values |
|-------|--------|
| `ticker` | `EXCHANGE:SYMBOL`, e.g. `NASDAQ:AAPL` |
| `type` | `SMA` or `EMA` |
| `length` | `5, 10, 20, 50, 100, 150, 200` |
| `timeframe` | `1H` (hourly) or `D` (daily) |

### Choosing a Timeframe

- **`1H`:** Checked at the top of every hour AND at 15:59 NY. Suitable for intraday traders.
- **`D`:** Checked only at 15:59 NY (end of day). Suitable for swing traders.

### Choosing a Length

| Length | Style | Notes |
|--------|-------|-------|
| `5–20` | Short-term | Sensitive; generates more signals |
| `50` | Medium-term | Common default |
| `100–200` | Long-term | Fewer signals, more trend-following |

---

## 7. Understanding Signals

### Signal Decision Table

| Condition | Decision |
|-----------|----------|
| `close < MA` AND `abv_be == True` | **SellSignal** — prepare sell |
| `close >= MA` | **NoSignal** — hold |
| `close < MA` but `abv_be == False` | **NoSignal** — position below break-even, do not sell |
| Insufficient data | **Skip** — not enough bars for MA |

### The `abv_be` Safety Gate

The tool only sells when the position is profitable enough that **both** the current close AND the MA value are above your average cost. This prevents selling at a loss during a temporary dip.

### Signal Log

Every signal is appended to `logs/signals.jsonl`:

```json
{"ticker":"NASDAQ:AAPL","decision":"SellSignal","close":182.45,"ma_value":185.20,"ts":"2026-04-04T15:59:00-04:00"}
```

---

## 8. Going Live

> **WARNING:** Live mode transmits real orders to your IB account.

1. **Paper trade first:** Test in a Paper Trading account until you are confident.
2. **Start with dry-run:** `python -m sellmanagement`
3. **Review signals:** Check `logs/signals.jsonl` to confirm signals match your expectations.
4. **Enable live:** `python -m sellmanagement --live`
5. **Confirm each order:** When a `SellSignal` appears, type `YES` and press Enter to transmit.
6. **Scripted runs (advanced):** `python -m sellmanagement start --live --yes-to-all` skips the interactive confirmation. Use only when you fully accept automated transmission risk.
7. **Monitor:** Watch `logs/intents.jsonl` for order status.

---

## 9. Troubleshooting

| Problem | Solution |
|---------|----------|
| IB connection refused | Check IB Gateway/TWS is running. Verify port (default: `4001`). |
| Missing Python packages | Run `pip install -e .` and `pip install ".[gui]"`. |
| No positions detected | Check that IB Gateway/TWS is logged in. Verify paper trading vs live account. |
| MA value shows `-` | Verify the ticker in `assigned_ma.csv` matches the IB token format exactly. |
| Signals not generating | Check that `timeframe` is `1H` or `D` in `assigned_ma.csv`. Ensure market is open. |
| GUI won't start | Install GUI deps: `pip install ".[gui]"`. Check PySide6/qtpy installation. |
| Duplicate orders | The intent store (SHA256) prevents duplicates. Check `logs/intents.jsonl`. |
| Stale MA values | Delete `config/cache/*.ndjson` and restart to trigger full backfill. |
