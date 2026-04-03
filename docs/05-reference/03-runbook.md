# Operational Runbook

> **Version:** 1.0 | **Last Updated:** 2026-04-04

---

## 1. First-Run Setup

### 1a. Prerequisites

- Python 3.10+
- IB Gateway or TWS running on `127.0.0.1:4001` (default)
- IB account logged in (paper trading recommended for first use)

### 1b. Install

```bash
# Create and activate virtual environment
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# Install in editable mode
pip install -U pip
pip install -e .
pip install ".[gui]"    # GUI extras (PySide6/qtpy)

# Or install from requirements
pip install -r requirements.txt
```

### 1c. First Run

```bash
# CLI mode (dry-run, safe)
python -m sellmanagement

# GUI mode
python -m sellmanagement --gui
# or
python src/sellmanagement/gui/run_gui.py
```

On first run, the app creates:
- `config/assigned_ma.csv` (with header row)
- `logs/` directory
- `config/cache/` directory

---

## 2. Starting the Application

### 2a. CLI Mode

```bash
# Dry-run (default — orders prepared but not sent)
python -m sellmanagement

# With live mode (orders transmitted — requires explicit --live flag + YES confirmation)
python -m sellmanagement --live

# With no-regular-trading-hours restriction disabled (includes pre/post-market data)
python -m sellmanagement --no-rth

# Custom IB client ID (use different ID for each concurrent connection)
python -m sellmanagement --client-id 2
```

### 2b. GUI Mode

```bash
# From project root
python -m sellmanagement --gui

# Or from source
python src/sellmanagement/gui/run_gui.py

# Or use the provided batch file (Windows)
run.bat
```

The GUI auto-connects on startup using the saved host/port/client ID from Settings.

### 2c. IB Gateway vs TWS

| Environment | Port | Notes |
|-------------|------|-------|
| IB Gateway (SSL) | `4001` | Default |
| TWS (non-SSL) | `7496` | Legacy |
| TWS (paper trading) | `7497` | For testing |
| IB Gateway (paper) | `4002` | May vary |

---

## 3. Stopping the Application

### CLI

Press `Ctrl+C` to exit the minute loop cleanly.

### GUI

Close the window, or click the status light (●) in the top-right corner to disconnect.

---

## 4. Assigning Moving Averages

### Via CLI (interactive on first run)

The CLI prompts for assignment for each unassigned ticker:

```bash
python -m sellmanagement
# Output:
# Tickers requiring assignment:
#  - NASDAQ:AAPL
# Assign MA for NASDAQ:AAPL...
#  1) SMA 5    1H     2) EMA 5    1H
#  ...
# Selection [default 7]:    # press Enter for SMA(50) 1H default
```

### Via CLI (non-interactive)

```bash
python -m sellmanagement assign NASDAQ:AAPL SMA 50 --timeframe 1H
```

### Via GUI

1. Open the **Positions** tab.
2. Click the **MA Type** dropdown and select `SMA` or `EMA`.
3. Enter the **MA Length** (5–200).
4. Select the **Timeframe** (`30m`, `1H`, or `D`).
5. Changes save automatically to `config/assigned_ma.csv`.

---

## 5. Daily Workflow

### Morning

1. Start IB Gateway / TWS and log in.
2. Start the app in dry-run mode: `python -m sellmanagement`
3. Confirm positions are detected.
4. Verify assigned MAs are correct.

### During Trading Day

- The app evaluates signals at the **top of every hour** and at **15:59 NY**.
- `SellSignal` entries appear in `logs/signals.jsonl`.
- In GUI, the **Signals** tab updates in real time.

### End of Day

- The 15:59 evaluation covers the daily close.
- Review `logs/signals.jsonl` for any `SellSignal` entries.
- If going to live mode, ensure `--live` flag is used and `YES` is typed at the confirmation prompt.

---

## 6. Recovery Procedures

### IB Gateway Disconnection

**Symptom:** `connected` status light turns red.  
**Automatic recovery:** The GUI's `IBWorker` schedules a reconnect with exponential backoff (1s → 60s).  
**Manual recovery:** Click the status light (●) in the GUI to reconnect.

### Resume from Sleep / Screensaver

**Symptom:** A `woke_late` trace event appears in `logs/ibkr_download_trace.log`.  
**Automatic recovery:** The app detects the gap and logs it. The next snapshot cycle resumes normal operation.  
**Manual check:** Verify the minute snapshot output after a long gap.

### Stale Cache

**Symptom:** MA values appear outdated.  
**Fix:** Delete `config/cache/*.ndjson` and restart the app to trigger a full backfill.

### Duplicate Order Prevention

The app uses SHA256 intent IDs (`{ticker}:{bucket_ts}:{decision}`). If the app restarts during a live order attempt, the intent store prevents re-submission of the same order.

---

## 7. Monitoring Log Files

```bash
# Tail signals log
Get-Content logs\signals.jsonl -Tail 10 -Wait

# Tail trace log
Get-Content logs\ibkr_download_trace.log -Tail 10 -Wait

# Count signals by type
(Get-Content logs\signals.jsonl | ConvertFrom-Json | Where-Object {$_.decision -eq "SellSignal"}).Count
```

---

## 8. Switching to Live Mode

> **WARNING:** Live mode transmits real orders to your IB account.

1. Test thoroughly in **paper trading** first.
2. Start with dry-run: `python -m sellmanagement`
3. Review the signals in `logs/signals.jsonl`.
4. Switch to live: `python -m sellmanagement --live`
5. When a `SellSignal` appears, type `YES` at the confirmation prompt to transmit the order.
6. Monitor `logs/intents.jsonl` for order status.
