Disclaimer: Use at your own risk. The repository owner and contributors accept no liability for trading losses arising from use of this software. By using this tool you acknowledge and accept the financial risks; test thoroughly in a Paper Trading account before enabling live mode.

# sellmanagement — Automated sell-preparation CLI

A small, safe command-line tool that watches your Interactive Brokers (IB) positions and prepares full-close sell orders when a position closes below an assigned moving average. The default mode is dry-run: orders are prepared and logged but never sent.

Why use this tool
-----------------
- Automates a single conservative rule: when a position's latest close is strictly below its assigned moving average at the top of the hour, the tool prepares a full-close sell order for that position.
- Keeps a clear audit trail in `logs/signals.jsonl` so you can review every prepared action.

Important behavior (read first)
--------------------------------
- **Positions and open orders are refreshed every minute and printed to your terminal.**
- **Signals are only generated at the exact top of each hour.** The app monitors continuously but evaluates sell rules only at that boundary. For end-of-day signals, the app uses 15:59:55 (America/New_York).
- **Signal Conditions:** the signal is only generated if the price is above break-even and the assigned MA is also above break-even.
- **New Positions:** when new positions are added, restart the app so that the historical data is downloaded.
- **Current behavior:** when a sell condition is met the app prepares a full-close of the entire position. Partial sells are NOT supported in this version.

Prerequisites
-------------
- Python 3.10 or newer. Download: `https://www.python.org/downloads/`
- Interactive Brokers Gateway or Trader Workstation (TWS) installed and running locally. Download page (IB Gateway & TWS): `https://www.interactivebrokers.com/en/index.php?f=16040`
- Recommended: use an IB Paper Trading account when testing.

Quick start (copy-paste)
------------------------
Open a terminal (Windows PowerShell, macOS Terminal, Linux shell) and run these commands.

1) Clone the repository (or download and extract the zip):

```bash
# with git installed
git clone https://example.com/your-repo/sell_manager_CLI.git
cd sell_manager_CLI
```

2) Create and activate a Python virtual environment, then install dependencies:

```bash
python -m venv .venv
# Windows PowerShell
.\\.venv\\Scripts\\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# Recommended: install the package in editable mode so the `sellmanagement` module is importable
pip install -U pip
pip install -e .

# Optional GUI dependencies (Qt/PySide):
pip install ".[gui]"
```

If `requirements.txt` is not present, install the core packages manually:

```bash
pip install ib_insync pandas numpy pyarrow pytest
```


3) Run the app in dry-run (safe) mode

```bash
# After `pip install -e .` you can run the CLI:
python -m sellmanagement

# To launch the GUI (after installing GUI extras):
python -m sellmanagement --gui

# Alternatively, run the GUI directly from source (no install):
python src/sellmanagement/gui/run_gui.py
```

What this does:
- Connects to IB on `127.0.0.1:4001` by default.
- Fetches positions and open orders.
- Downloads recent market data and computes configured MAs.
- Updates the positions table every minute and evaluates signals at the top of each hour.
- Appends signal audit records to `logs/signals.jsonl`.

Note: This repository uses a `src/` layout. Running `python -m sellmanagement` without installing the package may fail unless you set `PYTHONPATH=./src` or run `pip install -e .` first.

4) Edit assigned-MA CSV (example)

The tool uses the file `assigned_ma.csv` to record which moving average to apply to each ticker. After the first run, you can manually edit `config/assigned_ma.csv` with this example contents:

```csv
ticker,type,length,timeframe
NASDAQ:AAPL,SMA,50,1H
NYSE:IBM,EMA,200,1H
NASDAQ:MSFT,SMA,20,1H
```

Field notes:
- `ticker` should be `EXCHANGE:TICKER`, e.g. `NASDAQ:AAPL`.
- `type` is `SMA` or `EMA` (case-insensitive).
- `length` must be one of: `5, 10, 20, 50, 100, 150, 200`.
- `timeframe` for this release should be `1H` (hourly evaluation) or `1D` (daily evaluation)

Switching to live mode (WARNING — sends real orders)
---------------------------------------------------
Live mode transmits orders to your IB account. Use only after careful testing in a Paper Trading account.

```bash
python -m sellmanagement --live
```

Configuration & files
---------------------
- `config/assigned_ma.csv` — mapping of tickers to MAs (example above).
- `logs/signals.jsonl` — append-only audit log for all prepared signals and actions.
- `config/cache/` — internal cache of downloaded market data.

Interpreting CLI output
----------------------
On start and after each update you will see a compact table per ticker showing:
- `ticker`, `latest close`, `assigned MA`, `MA value`, `percent distance`, `position size`, `open orders`, and `abv_be` (a safety flag used internally).

At the top of each hour, when a sell condition is met, a signal is printed and written to `logs/signals.jsonl` containing timestamp, ticker, close, ma_type, ma_value, distance_pct, and action details.

Common troubleshooting
----------------------
- IB connection refused: confirm IB Gateway or TWS is running and logged in. Common IB API ports are `4001` (IB Gateway SSL), `7496` (TWS non-SSL), and `7497` (TWS paper-trading). The app defaults to `127.0.0.1:4001` unless configured otherwise.
- Missing Python packages: run `pip install -e .` and for developer/test tools `pip install -r requirements-dev.txt` (or install packages listed in `pyproject.toml`).
- Permission errors writing logs: run the app in a folder where you have write permissions.

Contributing & tests
--------------------
- Tests use `pytest`. To run tests from the project root:

```bash
pytest -q
```

Please run tests locally and validate order flows in a Paper Trading account before using `--live`.

Support
-------
If you need help, open an issue or contact the repository owner. Include `logs/signals.jsonl` and your `config/assigned_ma.csv` when requesting help.

Changelog & status
------------------
This release implements the CLI, data download, MA computation, and signal logging. Remaining work in the project roadmap includes improved live-mode safety (global caps, idempotency tokens) and an adaptive rate-limiter for IB pacing.

License
-------
See `LICENSE` in the repository root.
