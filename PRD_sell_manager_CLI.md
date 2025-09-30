# Product Requirements Document — **sellmanagement** (CLI)

**Status:** Draft — implements a small, self-contained, testable CLI that mirrors a subset of the Dolichart GUI behavior (methodologies folder used as reference), with emphasis on safety, small incremental wins, and clear structure.

---

## 1 — Purpose & scope

**Purpose:** build a minimal, standalone CLI app (`sellmanagement`) that continuously monitors IBKR positions and automatically *prepares* (but **does not send** in test mode) full-close sell orders when a position closes below an assigned moving average at the turn of the hour.

**Scope (what this project will do):**

* Connect to IB Gateway (local host) on port  **4001** , fetch current positions and related open orders. ([Interactive Brokers](https://www.interactivebrokers.com/download/IB-Host-and-Ports.pdf?utm_source=chatgpt.com "IB-Host-and-Ports.pdf"))
* For each `[exchange]:[ticker]` found in positions, download:
  * 1 year of **daily** bars, and
  * 31 days of **30-minute** bars (which we will compile to hourly bars).

    Use asynchronous downloading with rate-limiting (batches of 32 concurrent requests recommended; see implementation). Observe IB historical-data pacing limits. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))
* Cache all fetched data on disk; compute and cache EMA & SMA for durations: `5, 10, 20, 50, 100, 150, 200` for both daily and hourly timeframes.
* Every  **minute** : fetch last 7 days of daily and last 1 day of hourly data, merge with cache, update MAs and status table.
* Every **hour** (turn of the hour): evaluate signals; if price closed **below** the assigned MA for that position, **prepare** a full-close order (dry-run by default). On live mode, send order to IB after multiple safety checks. Also cancel any other open orders for that position after close. Use atomic checks to avoid mismatched sizes.
* Logging: record every hourly signal and the computed metrics to a directory file (CSV/JSONL) for audit. Include a `part_time_larry.py` helper that demonstrates the logging format and simple sample code.

**Non-goals / out of scope**

* GUI (this is CLI-only).
* Cross-project dependencies — `sellmanagement` must be independent and NOT import project internals from Dolichart or others.
* Complex strategy engineering: only single rule (close below assigned MA → prepare/sell) for this initial project.

---

## 2 — Assumptions & constraints

* App will connect to **IB Gateway / TWS** running locally (default host `127.0.0.1`, port  **4001** ). ([Interactive Brokers](https://www.interactivebrokers.com/download/IB-Host-and-Ports.pdf?utm_source=chatgpt.com "IB-Host-and-Ports.pdf"))
* Use IB’s historical data carefully — IB imposes pacing/soft limits; large/fast historical requests can be throttled or disconnect clients. We will rate-limit and batch requests. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))
* During development the default mode is  **dry-run / read-only** ; orders are prepared and logged but not transmitted. For live mode require explicit flags + pre-conditions (see Safety).
* Keep every source file short (target  **< 300 lines** ). Keep single responsibility per module.

---

## 3 — Key functional requirements (FR)

1. **FR1 — Start-up connect**
   * Connect to IB Gateway (host, port 4001) and fetch **positions** and **open orders** for the account. Use `reqPositions` / `reqPositionsMulti` (or ib_insync helpers). ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/positions.html?utm_source=chatgpt.com "TWS API v9.72+: Positions - Interactive Brokers - API Software"))
2. **FR2 — Ticker normalization**
   * Convert each position to `[exchange]:[ticker]` string and queue for historical downloads.
3. **FR3 — Data download & caching**
   * For each ticker: download 1Y daily bars and 31D 30m bars asynchronously. Use batching and concurrency limit  **32** . Merge 30m into hourly bars after fetch. Cache to disk (efficient format: parquet or feather or SQLite). Observe IB pacing/limits. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))
4. **FR4 — Indicators**
   * Compute SMA and EMA for durations `5,10,20,50,100,150,200` for daily & hourly timeframes; cache results.
5. **FR5 — CLI status output**
   * On start and after each update, print a table per ticker with:
     * ticker, latest close, percent change to cross below each MA, assigned MA (which MA is assigned to a position must be configurable), MA value at close, position size, corresponding open orders.
6. **FR6 — Continuous updater**
   * Every minute: fetch 7D daily + 1D hourly, merge, recompute MA, update CLI table.
7. **FR7 — Hourly signal & action**
   * On each top-of-hour boundary: evaluate if close < assigned MA → generate **close** signal. In **dry-run** mode: log and print signal. In **live** mode: run safety checks, then submit sell order for exact current position size and cancel other open orders for that position.
8. **FR8 — Audit logging**
   * Append hourly signals to `signals.log` in CSV or JSON lines with: timestamp, ticker, close, MA_type (SMA/EMA + length), MA_value, distance_pct, action_prepared, action_executed, order_id (if sent), errors.
9. **FR9 — Config & CLI flags**
   * `--config FILE`, `--dry-run` (default), `--live`, `--log-dir`, `--client-id`, `--concurrency`, `--cache-dir`.
10. **FR10 — Tests**
    * Granular unit tests for downloader, aggregator (30m→hour), MA calculators, signal decision, order preparation, and integration test harness using a paper account or mock IB.

---

## 4 — Non-functional requirements (NFR)

* **NFR1 — Reliability:** resilient to IB socket disconnects; auto-retry with exponential backoff and reconnection logic. (TWS sockets will break occasionally; design to reconnect.) ([Waste of Server](https://wasteofserver.com/interactive-brokers-tws-gateway-api-and-yet-it-works/?utm_source=chatgpt.com "Interactive Brokers TWS API - and yet it works! - Waste of Server"))
* **NFR2 — Safety:** dry-run by default; explicit `--live` flag required to actually send orders. Must support TWS/IBG “Read-only API” toggles for extra safety during development. ([Algo Trading 101](https://algotrading101.com/learn/interactive-brokers-python-api-native-guide/?utm_source=chatgpt.com "Interactive Brokers Python API (Native) - A Step-by- ..."))
* **NFR3 — Observability:** human-readable CLI tables + log files + structured logs for debugging.
* **NFR4 — Maintainability:** modules small (<300 lines), clear directory layout, typed Python (mypy), linting & pre-commit hooks.
* **NFR5 — Performance:** concurrent downloader limited to `concurrency` (default 8–32, configurable). Disk cache for efficient startup.

---

## 5 — Detailed workflows

### Start-up (exact sequence)

1. Load Assigned MAs (first step)
   * Before connecting to IB, read the assigned-MA CSV at `config/assigned_ma.csv` mapping each ticker (in `[exchange]:[ticker]` format) to its assigned moving average and timeframe. The CSV columns should be: `ticker,type,length,timeframe` (for example: `NASDAQ:AAPL,SMA,50,1H`).
   * If a live IB position exists that is not present in the CSV, the app will prompt the user interactively, one ticker at a time, to select an assigned MA and timeframe. The interactive flow is:
     1. Show the ticker token.
     2. Prompt to choose MA family from a numbered list (e.g. 1) SMA, 2) EMA).
     3. Prompt to enter MA length (default shown, e.g. 50).
     4. Prompt to choose timeframe from a numbered list (e.g. 1) 1H, 2) D).
     5. Persist the selection to `config/assigned_ma.csv` and continue to the next missing ticker.
     This interactive assignment is the default at startup; it repeats until all missing tickers have assignments.
   * This file serves as the source of truth for which MA (and timeframe) is used when evaluating signals at runtime.
2. Read config, set `dry-run=True` unless `--live` passed. Ensure `--client-id` unique and validate any CLI flags.
3. Connect to IBG/TWS: `ib.connect(host, 4001, clientId=...)`.  **(port 4001 is the IBG/TWS SSL port)** . ([Interactive Brokers](https://www.interactivebrokers.com/download/IB-Host-and-Ports.pdf?utm_source=chatgpt.com "IB-Host-and-Ports.pdf"))
4. Call `positions = ib.positions()` (or `reqPositionsMulti` for specific groups). Also fetch `openOrders = ib.openOrders()`. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/positions.html?utm_source=chatgpt.com "TWS API v9.72+: Positions - Interactive Brokers - API Software"))
5. Build list of tickers as `[exchange]:[ticker]` and queue them for downloads (only include tickers with assigned MAs unless user indicates otherwise).
6. Start asynchronous downloads for each ticker:
   * Request 1Y daily bars (`durationStr='1 Y'`, `barSize='1 day'`).
   * Request 31D 30m bars (`durationStr='31 D'`, `barSize='30 mins'`).
   * Use concurrency semaphore (default `32`) and batching to avoid pacing violations. Merge 30m → hourly.
   * On receipt, cache raw bars and computed indicators.
   * The downloader should honor historical-data pacing rules and exponential backoff on pacing errors. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))
7. After initial data cached, compute all MAs (for all configured lengths) and print the status table; for signals use the assigned MA from `config/assigned_ma.csv`.

### Minute updater

* At **start of every minute** (when system clock ticks to next minute):
  * Fetch 7D daily + 1D hourly history for each ticker (small requests).
  * Merge into cache, recompute MAs for changed bars, update CLI table.

### Hourly evaluator & order flow

* On  **exact top-of-hour** :
  * For each position:
    1. Check last closed price and assigned MA value.
    2. If `close < MA` → prepare close signal.
    3. Double-check live position size via `ib.positions()` (to ensure no drift), and current open orders (`ib.openOrders()`).
    4. Prepare an order for  **exact position size** . In dry-run: log & print action (no send). In live mode:
       * Re-check size (atomic read), then place a market/limit order as configured.
       * Cancel any other open orders associated with that position after execution or as part of a coordinated sequence.
    5. Log everything to `signals.log`.
* **Important:** implement idempotency and ordering semantics so that reconnects or crashes do not re-submit duplicate orders.

---

## 6 — Data & caching

* **Cache format:** parquet (fast, typed) or lightweight SQLite table; store raw bars and computed MA tables separately to avoid recompute.
* **Cache keys:** `exchange:ticker:granularity` (e.g. `NASDAQ:AAPL:1d`, `NASDAQ:AAPL:30m`, `NASDAQ:AAPL:1h`).
* **Retention:** keep at least 1Y daily + 31D of 30m (or longer if desired). Provide manual cache rebuild script.

---

## 7 — Rate-limiting & historical-data limits

* IB historically enforces pacing for historical requests; **do not** flood with identical historical queries. Implement:
  * Concurrency semaphore (default concurrency  **32** ) for historical requests.
  * A global per-minute/hour bucket with exponential backoff on pacing errors.
  * Batch downloads so you request `n` tickers per round and sleep between rounds if necessary.
* Prioritize daily over intraday if forced. For intraday 30m → compile to hourly, reducing frequency of requests.
* **References:** IB historical limitations and valid bar sizes / durations. Use these rules to select duration and bar sizes programmatically. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))

---

## 8 — Safety & order precautions (very important)

* **Default dry-run:** yes. Orders are only prepared & logged (never submitted) unless `--live` is set and multiple gating checks pass.
* **Use Paper Trading for testing:** always validate on IB paper account before live. ([Interactive Brokers](https://www.interactivebrokers.com/campus/trading-lessons/how-to-open-an-ibkr-paper-trading-account/?utm_source=chatgpt.com "How to Open an IBKR Paper Trading Account"))
* **Read-only API & TWS settings:** during early testing enable “Read-Only API” / “Enable ActiveX and socket clients” appropriately in TWS/IBG to avoid accidental live orders. ([Algo Trading 101](https://algotrading101.com/learn/interactive-brokers-python-api-native-guide/?utm_source=chatgpt.com "Interactive Brokers Python API (Native) - A Step-by- ..."))
* **Pre-order checks:**
  * Re-fetch server position (authoritative) and open orders immediately before submit. If mismatch, abort and log.
  * Limit maximum order sizes and add a global daily limit to prevent runaway behavior.
  * Require a one-time confirmation (CLI prompt) to enable live mode; require a config secret or environment var for live.
  * Use order `transmit=False` when submitting advanced orders then inspect and `transmit=True` only after final checks (if using IB advanced orders).
* **Audit trail:** every prepared/sent order must be recorded with full context (pre-check positions, order JSON, IB response).
* **Retries:** if order fails due to transient IB error, apply limited retries with exponential backoff; if non-transient (rejection), stop and alert.

---

## 9 — Outstanding questions — answers & recommendations

**Q: Will screensaver stop the app overnight?**

* The screensaver itself only changes what is shown on the display; it does **not** stop background processes. **Sleep/hibernate** will suspend processes and must be disabled if you want the app to keep running. On Windows, change Power & Sleep settings to prevent sleep when plugged in (or use `powercfg`), or use a small "keep awake" tool like `caffeinate` on macOS. See Microsoft docs on sleep vs screen off. ([Microsoft Learn](https://learn.microsoft.com/en-us/answers/questions/4128431/what-is-the-difference-between-sleep-mode-and-your?utm_source=chatgpt.com "What is the difference between sleep mode and your ..."))

**Q: Best practices for code structure & maintainability?**

* Single responsibility, small files (<300 lines), typed interfaces, dependency inversion for IB client so you can inject mocks. Use `pyproject.toml`, black, flake8, pre-commit, CI with GitHub Actions. Keep each module focused: downloader, ib_client, cache, indicators, signals, orders, cli. Add a `README` and developer doc (methodologies matching Dolichart folder style).

**Q: Which modules/packages?** (recommended)

* **Runtime/API:** `ib_insync` — friendly high-level asyncio wrapper for IB API (sync + async helpers). ([ib-insync.readthedocs.io](https://ib-insync.readthedocs.io/api.html?utm_source=chatgpt.com "API docs — ib_insync 0.9.86 documentation"))
* **Data:** `pandas`, `numpy`, `pyarrow` (for parquet), `diskcache` or `sqlite3` (for persistent small cache).
* **Indicators:** `pandas_ta` (pure Python) or `ta-lib` (C dependency; only if you can manage native install).
* **Async & networking:** `asyncio`, optionally `aiohttp` / `httpx` if you use web APIs.
* **Testing:** `pytest`, `pytest-mock`.
* **Formatting/linting:** `black`, `ruff` or `flake8`, `mypy`.
* **Optional:** `docker` to run IB Gateway in CI or local integration tests (community images exist). ([GitHub](https://github.com/gnzsnz/ib-gateway-docker?utm_source=chatgpt.com "Docker image with IB Gateway/TWS and IBC"))

**Q: Lightweight charts: will they auto-update?**

* If charts subscribe to the same cache or use a pub/sub notification from the updater, they can update automatically. For a CLI, simple ASCII tables are fine. If you embed a lightweight charting component later (web UI or electron), implement a small websocket or file-watch mechanism that triggers chart refresh when cache updates.

**Q: Order component risk precautions?**

* See Safety section above: read-only mode, paper trading, explicit `--live` flag, double-check server positions just before submit, global caps/limits, audit logs, and require multi-factor or operator confirmation for live enablement.

---

## 10 — Implementation plan (small wins / milestones)

*(Keep each milestone small, testable, and visible. Files <300 lines.)*

**Milestone 0 — Repo & CI**

- ~~Repo skeleton, `pyproject.toml`, basic README, GitHub Actions running tests (empty tests pass).~~
- ~~Add `Makefile` with common commands.~~

**Milestone 1 — IB connection & positions (small win)**

- ~~File: `ib_client.py` — connect/disconnect + fetch positions and open orders (dry-run).~~
- ~~CLI command: `sellmanagement start --dry-run` prints positions table.~~
- ~~Tests: unit test that `ib_client` returns positions using a mocked IB object.~~

**Milestone 2 — Historical downloader & cache**

- ~~File: `downloader.py`, `cache.py`. Implement async downloader with concurrency semaphore (configurable, default 32). Download daily + 30m and store in cache.~~
- ~~Small win: run start-up and see cached parquet files created.~~

**Milestone 3 — Indicators & tables**

- ~~File: `indicators.py`. Compute SMA/EMA durations and cache results.~~
- ~~CLI: print per-ticker MA table showing distance to MAs.~~

**Milestone 4 — Minute updater**

- ~~File: `updater.py`. Implement minute scheduler and data merging. CLI shows updated tables every minute.~~
- ~~Small win: observe updates and printed messages.~~

**Milestone 5 — Hourly evaluator & logging**

- ~~File: `signals.py`, `part_time_larry.py` (sample logger). Implement hourly evaluation and logging to `signals.log` (CSV/JSONL).~~
- ~~Small win: At top of hour, generate signal and append to `signals.log` (dry-run).~~

**Milestone 6 — Order preparation & safety checks**

- ~~File: `orders.py`. Prepare orders and implement final checks (re-fetch positions, compare sizes). In dry-run no submit. Add `--live` gate.~~
- ~~Tests: mock IB and assert order prepared with exact size.~~

**Milestone 7 — Integration tests & paper trading**

* Integration harness that runs against IB Paper account or IB Gateway docker image. Add scenarios: connectivity loss & reconnect, pacing error handling, and order rejection handling.

**Milestone 8 — Optional charts**

* Add `charts/` module to serve minimal web UI with small charts that reload on cache update.

---

## 11 — Directory layout (suggested)

```
sellmanagement/
├─ pyproject.toml
├─ README.md
├─ LICENSE
├─ src/
│  ├─ sellmanagement/
│  │  ├─ __main__.py          # CLI entry (small)
│  │  ├─ config.py            # Config dataclass & defaults
│  │  ├─ ib_client.py         # IB connection wrapper (~<300 lines)
│  │  ├─ downloader.py        # async downloads + rate limiting
│  │  ├─ cache.py             # disk cache helpers
│  │  ├─ indicators.py        # SMA/EMA calc
│  │  ├─ updater.py           # minute/hour schedulers
│  │  ├─ signals.py           # hourly evaluation + logging
│  │  ├─ orders.py            # order creation & safety checks
│  │  ├─ logger.py            # structured logging helpers
│  │  └─ part_time_larry.py   # sample logging + simple example code
├─ tests/
│  ├─ test_ib_client.py
│  ├─ test_downloader.py
│  ├─ test_indicators.py
│  └─ integration/            # optional docker-based integration tests
└─ docs/
   ├─ methodologies/          # mirror of Dolichart style as references
   └─ API_README.md
```

Each module should target **< 300 lines** by splitting helper functions into submodules if needed.

---

## 12 — Example code snippets (short)

**IB connect & fetch positions (ib_insync)**

```python
# src/sellmanagement/ib_client.py (excerpt)
from ib_insync import IB

class IBClient:
    def __init__(self, host='127.0.0.1', port=4001, clientId=1):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId

    def connect(self):
        self.ib.connect(self.host, self.port, clientId=self.clientId, timeout=10)
        return self.ib.isConnected()

    def get_positions(self):
        # returns list of Position(contract, position, avgCost) objects
        return self.ib.positions()

    def get_open_orders(self):
        return self.ib.openOrders()

    def disconnect(self):
        self.ib.disconnect()
```

**Async downloader with concurrency semaphore (concept)**

```python
# src/sellmanagement/downloader.py (concept)
import asyncio
from asyncio import Semaphore

async def fetch_historical(ib, contract, duration, bar_size):
    # wrapper to call ib.reqHistoricalData or ib_insync API (blocking->wrap in executor)
    pass

async def download_batch(ib, contracts, concurrency=32):
    sem = Semaphore(concurrency)
    async def worker(c):
        async with sem:
            return await fetch_historical(ib, c, '1 Y', '1 day')
    results = await asyncio.gather(*(worker(c) for c in contracts))
    return results
```

**Signal logger (part_time_larry.py example)**

```python
# src/sellmanagement/part_time_larry.py
import csv
from datetime import datetime

def log_signal(path, record):
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().isoformat(),
            record['ticker'],
            record['close'],
            record['ma_type'],
            record['ma_value'],
            record['distance_pct'],
            record['action_prepared'],
            record.get('order_id','')
        ])
```

---

## 13 — Testing strategy

* **Unit tests:** pure functions (MA calc, aggregator, small-state logic). Use `pytest`. Keep tests deterministic with seed data.
* **Mocked IB tests:** mock `ib_insync.IB` methods (`positions`, `openOrders`, `reqHistoricalData`) using `pytest-mock` to test downloader & order prep.
* **Integration tests:** run against IB Paper account or IB Gateway Docker image in local CI job (optional gating). Use Docker image to spin IBG and run a small end-to-end scenario. ([GitHub](https://github.com/gnzsnz/ib-gateway-docker?utm_source=chatgpt.com "Docker image with IB Gateway/TWS and IBC"))
* **Safety tests:** assert that `--dry-run` never calls `ib.placeOrder()` in unit/integration runs unless `--live` is set and confirm gate is passed.

---

## 14 — Operational notes & monitoring

* **Run mode:** systemd service on Linux or scheduled process. Ensure system sleep is disabled; screen off is ok. Use `caffeinate` or `powercfg` / macOS `pmset` if needed. ([Microsoft Learn](https://learn.microsoft.com/en-us/answers/questions/4128431/what-is-the-difference-between-sleep-mode-and-your?utm_source=chatgpt.com "What is the difference between sleep mode and your ..."))
* **Monitoring:** stdout logs + file logs + optional push notifications/email if an error occurs (e.g., repeated IB disconnect).
* **Backups:** rotate `signals.log` daily and archive.

---

## 15 — Next steps / recommended immediate actions

1. Create repo skeleton and `pyproject.toml`.
2. Implement **Milestone 1** (IB connection + positions) using `ib_insync`. Validate locally against an IB paper account. (Small, visible win: `python -m sellmanagement` prints positions).
3. Implement downloader (Milestone 2) with concurrency=8 first, then tune to 32 once stable.
4. Add unit tests and CI.

---

## 16 — References & important docs

* IB TWS API docs (positions, historical bars): official documentation. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/positions.html?utm_source=chatgpt.com "TWS API v9.72+: Positions - Interactive Brokers - API Software"))
* IB Host & Ports (port 4001 reference). ([Interactive Brokers](https://www.interactivebrokers.com/download/IB-Host-and-Ports.pdf?utm_source=chatgpt.com "IB-Host-and-Ports.pdf"))
* ib_insync docs — high-level Python wrapper (recommended). ([ib-insync.readthedocs.io](https://ib-insync.readthedocs.io/api.html?utm_source=chatgpt.com "API docs — ib_insync 0.9.86 documentation"))
* IB Client Portal API pacing (note: web client has 10 RPS global) — check if using Client Portal API. ([Interactive Brokers](https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/?utm_source=chatgpt.com "Web API v1.0 Documentation"))
* Historical data limitations and valid bar sizes (how far back / barSize restrictions). ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))

---






## 🔹 Updated Startup Flow

1. **Load Assigned MAs (first step)**
   * At app launch, before connecting to IB, the app should **read a configuration file** that maps each ticker (in `[exchange]:[ticker]` format) to its  **assigned moving average** .
   * Example: `NASDAQ:AAPL → SMA(50)`, `NYSE:IBM → EMA(200)`.
   * If a position exists in IB but has no assigned MA in the file, the app prompts the user in CLI to assign one (or assign a default rule like `SMA(50)` if running unattended). The new assignment is then written back into the file so it persists for the next run.
   * This ensures the **user is always aware and in control of the MA assignment** before signals are evaluated.
2. **Proceed with the rest of the startup**
   * Connect to IB Gateway (port 4001).
   * Fetch positions and open orders.
   * Start historical data downloads & cache building.
   * Compute indicators (all durations), but for signals use the *assigned* MA for each ticker.

---

## 🔹 Assigned-MA storage (chosen: CSV)

We will use a CSV file as the canonical storage for assigned moving averages. This format is simple, editable in Excel, and interoperable with the traders' workflows.

- **Location**: `config/assigned_ma.csv` (create `config/` if missing)
- **Format (header)**: `ticker,type,length`
- **Example rows**:

```csv
ticker,type,length
NASDAQ:AAPL,SMA,50
NYSE:IBM,EMA,200
NASDAQ:MSFT,SMA,20
```

Notes:
- Keep values normalized: `type` must be `SMA` or `EMA` (case-insensitive on read, normalized to upper-case on write), `length` is a positive integer from the supported set (`5,10,20,50,100,150,200`).
- On startup the app will load `config/assigned_ma.csv`, validate the schema, and coerce/repair trivial issues (e.g., trim whitespace). Any malformed rows should be logged and skipped; the CLI should report them for user correction.

## 🔹 How the App Should Use It

* **At startup**: load `config/assigned_ma.csv` and validate entries. For any IB positions missing from the CSV, prompt user interactively to assign an MA (or assign a configurable default like `SMA,50` in unattended mode) and persist the new row to the CSV.
* **During runtime**: use the CSV as the authoritative mapping when evaluating signals; changes to `config/assigned_ma.csv` require a restart to take effect (or future enhancement: watch file and reload safely).

## 🔹 Best Practice for Implementation

* Store and read the CSV with Python's built-in `csv` module or `pandas` when appropriate for batch operations.
* Provide a small CLI helper to update assignments without manual CSV edits, for example:

```bash
sellmanagement assign NASDAQ:AAPL SMA 50
```

This command should validate inputs, append or update the `config/assigned_ma.csv`, and print a confirmation.

---

## 🔹 Cross-project references for implementation

Use these concrete files and patterns as implementation references (read-only inspiration — do not import code directly):

- **Dolichart (`dolichart/`) — key files to review:**
  - `dolichart/ibkr/components/connection_manager.py` — persistent IB connection lifecycle, attach/detach handlers, robust start/stop, and safe initial positions fetch.
  - `dolichart/ibkr/components/service_orchestrator.py` — orchestration pattern that composes connection, downloader, real-time manager and rate limiter; good for structuring a single shared IB service.
  - `dolichart/ibkr/components/real_time_manager.py` — market-data subscription pooling and reqId bookkeeping (subscribe/unsubscribe patterns).
  - `dolichart/strategies/ma_exit/scheduler.py` — decision-window logic, duplicate-suppression, and how to call into a signal handler without embedding IB specifics.
  - `dolichart/strategies/ma_exit/signal_log.py` — signal audit format (JSONL) and append pattern used across the project.
  - `dolichart/ibkr/components/rate_limiter.py` (and adaptive limiter usage in orchestrator) — for handling pacing/backoff rules.

- **Snappy (`Snappy/`) — .NET IB client patterns:**
  - `Snappy/Snappy/InteractiveBrokers/Client.cs` — production-grade socket read loop, status state machine, message dispatching and error handling; useful to study message-based state transitions, reconnection semantics and status flags.
  - `Snappy/Snappy/InteractiveBrokers/Request.cs` and `Snappy/Snappy/InteractiveBrokers/Client.Request.cs` — examples of request/response flow and request id management.

- **Parttimelarry examples (`Parttimelarry_examples/`) — simple samples:**
  - `Parttimelarry_examples/sample_1.py`, `Parttimelarry_examples/sample_2.py` — quick async IB interaction and logging examples; useful for the `part_time_larry.py` sample and CSV/JSONL formatting conventions.

What to cross-check / borrow as patterns:

- Connection lifecycle & reconnection: prefer the `ConnectionManager` start/connect loop that tries multiple ports/client-ids, attaches portfolio/order events, and exposes a safe `get_latest_positions_normalized()` snapshot.
- Single shared IB instance: use an orchestrator-like pattern (`IbkrServiceOrchestrator`) to centralize connection, downloader, real-time subscriptions and rate limiting.
- Rate-limiting & prefetch: adapt the adaptive rate limiter and prefetch queue patterns from `dolichart/ibkr/components` to avoid IB pacing violations.
- Real-time pooling: follow `RealTimeManager` to avoid creating per-subscriber IB clients and to track reqId → symbol bookkeeping.
- Signal logging & idempotency: reuse the `ma_exit` scheduler's duplicate-suppression approach and the `signal_log.append_signal()` JSONL format for auditability.
- Request/response robustness: inspect `Snappy`'s message loop and error codes handling for ideas on demoting IB warnings, mapping server codes to connection states, and surfacing errors to the CLI.

Actionable note for implementers: when reusing patterns from `dolichart/` and `Snappy/`, copy the architectural idea and tests but implement fresh, small, well-scoped modules in `sellmanagement/` (keep files < 300 lines). Ensure unit tests cover reconnection, rate-limiter behavior, and that `--dry-run` never calls `placeOrder()` in tests.
