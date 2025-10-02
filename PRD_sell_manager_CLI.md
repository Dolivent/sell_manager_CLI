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

    Use asynchronous downloading with rate-limiting (batches of 32 concurrent requests recommended; see implementation). Observe IB historical-data pacing limits. Note for 30-minute (intraday) data:

    - IB historically returns up to ~31 bars per historical-data request for many intraday parameter combinations. To compute long moving averages (up to 200 periods) on an hourly series we need more than a single 31-bar slice; therefore at startup the downloader will fetch multiple sequential 31-bar slices for each ticker and stitch them together until we have enough 30m bars to aggregate to hourly and compute MAs up to the configured maximum length.
    - The per-ticker multi-slice backfill must be executed sequentially (one slice after another) to avoid pacing violations for that symbol, while the overall startup downloader may run per-ticker backfills concurrently across different tickers.
    - For minute-level updates (the regular snapshot flow) we will only request a single short 31-bar 30m slice and merge/aggregate it into the hourly cache — no multi-slice backfilling on the minute path. This keeps minute snapshots fast and low-cost.
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
  * If a live IB position exists that is not present in the CSV, or if the CSV contains rows with missing assignment fields, the app will prompt the user interactively to assign each missing ticker. The interactive flow is simplified to a single selection per ticker for speed and consistency:
    1. Show the ticker token.
    2. Present a single numbered list of MA choices where each line displays two options side-by-side: **SMA** on the left and **EMA** on the right for the supported MA lengths and timeframes. Example (two columns per line):

       1) SMA  5 1H        2) EMA  5 1H
       3) SMA 10 1H        4) EMA 10 1H
       5) SMA 20 1H        6) EMA 20 1H
       ...

    3. The user enters one number to choose the desired MA (a sensible default is shown).
    4. The selected MA (family, length, timeframe) is persisted to `config/assigned_ma.csv` and the app moves to the next missing ticker.
    Notes:
    - The prompt runs for both newly-discovered positions and any existing CSV rows that are incomplete (missing type, length, or timeframe).
    - There is no separate "no timeframe" option in the interactive picker; timeframes are explicitly selected as part of the single-number choice.
    - This interactive assignment is the default at startup; it repeats until all missing tickers have assignments.
   * This file serves as the source of truth for which MA (and timeframe) is used when evaluating signals at runtime.
2. Read config, set `dry-run=True` unless `--live` passed. Ensure `--client-id` unique and validate any CLI flags.
3. Connect to IBG/TWS: `ib.connect(host, 4001, clientId=...)`.  **(port 4001 is the IBG/TWS SSL port)** . ([Interactive Brokers](https://www.interactivebrokers.com/download/IB-Host-and-Ports.pdf?utm_source=chatgpt.com "IB-Host-and-Ports.pdf"))
4. Call `positions = ib.positions()` (or `reqPositionsMulti` for specific groups). Also fetch `openOrders = ib.openOrders()`. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/positions.html?utm_source=chatgpt.com "TWS API v9.72+: Positions - Interactive Brokers - API Software"))
5. Build list of tickers as `[exchange]:[ticker]` and queue them for downloads (only include tickers with assigned MAs unless user indicates otherwise).
6. Start asynchronous downloads for each ticker:
   * Request 1Y daily bars (`durationStr='1 Y'`, `barSize='1 day'`).
   * Request 31D 30m bars (`durationStr='31 D'`, `barSize='30 mins'`). For hourly-assigned tickers, perform a **sequential backfill** of 31-bar slices until at least `max_ma_length` (for example, 200) 30m bars are collected, then aggregate into hourly bars and persist both raw (30m) and aggregated (1h) caches.
   * Use a concurrency semaphore (default `32`) and batching to avoid pacing violations. Important: the sequence of 31-bar requests for a single ticker must run in series, but the downloader can run those sequences in parallel across different tickers.
   * On receipt, cache raw bars and computed indicators (persist both 30m and aggregated 1h series). Merge and dedupe by `Date` when combining slices.
   * The downloader should honor historical-data pacing rules and exponential backoff on pacing errors. ([Interactive Brokers](https://interactivebrokers.github.io/tws-api/historical_limitations.html?utm_source=chatgpt.com "TWS API v9.72+: Historical Data Limitations"))

   Implementation note (async bridge): to safely use `ib_insync` async helpers from worker threads, run a single background asyncio event loop that owns one connected `IB()` instance (an "AsyncIBBridge"). Worker threads should schedule async coroutines onto that loop using `asyncio.run_coroutine_threadsafe(...)` (or a small wrapper) and wait on the returned Future with a timeout. Benefits:
   - avoids "no current event loop in thread" errors
   - keeps a single IB connection context for async calls (prevents per-thread connection issues)
   - enables timeouts, tracing and centralized reconnect logic

   Operational guidance for the bridge:
   - start the bridge once at downloader startup; ensure it connects to IB in its own thread
   - schedule `reqHistoricalDataAsync` coroutines on the bridge loop and use `future.result(timeout=...)`
   - instrument each request with tracing and reasonable timeouts (e.g. 10–20s)
   - implement reconnect/backoff in the bridge thread if `IB` disconnects
   - fall back to sync `reqHistoricalData` only if async scheduling fails or times out
7. After initial data cached, compute all MAs (for all configured lengths) and print the status table; for signals use the assigned MA from `config/assigned_ma.csv`.

### Minute updater

* At **start of every minute** (when system clock ticks to next minute):
  * Fetch short recent bars for each ticker (implementation currently requests `2 D` for daily-assigned tickers and `1 D` half-hour slices for hourly-assigned tickers). For tickers assigned to hourly timeframe, aggregate the returned 30m slice to hourly and merge into the hourly cache.
  * Do NOT perform multi-slice backfills during minute snapshots — only the single short slice is requested and merged. This keeps per-minute CPU/network usage small.
  * Also fetch authoritative `positions()` and `openOrders()` from IB each minute (best-effort). Open orders are parsed for candidate stop prices (fields like `auxPrice`, `trailStopPrice`, `triggerPrice`, `stopPrice`) and associated to tickers using the returned `contract` when available or by inspecting textual fields (e.g. `ocaGroup` / `orderRef`).
  * Compute an additional per-ticker boolean field `abv_be` and include it in the snapshot and CLI table. `abv_be` is used as a safety gate for sell decisions and is currently defined as:
    - `True` when the snapshot `last_close` is strictly above the position `avgCost` AND the assigned `ma_value` is strictly above the position `avgCost`.
    - (Implementation note) previously `abv_be` also considered the presence of an open-order stop price below the MA; this was simplified to the above definition. We can change it to require both the price/MA conditions and a stop order below the MA if desired.
  * Merge into cache, recompute MAs for changed bars, update CLI table (the CLI now prints timeframe before the assigned MA, and sorts rows so tickers with `abv_be == True` appear first).

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

- Repo skeleton, `pyproject.toml`, basic README, GitHub Actions running tests (empty tests pass).
- Add `Makefile` with common commands.

**Milestone 1 — IB connection & positions (small win)**

- File: `ib_client.py` — connect/disconnect + fetch positions and open orders (dry-run).
- CLI command: `sellmanagement start --dry-run` prints positions table.
- Tests: unit test that `ib_client` returns positions using a mocked IB object.

**Milestone 2 — Historical downloader & cache**

- File: `downloader.py`, `cache.py`. Implement async downloader with concurrency semaphore (configurable, default 32). Download daily + 30m and store in cache.
- Implement **per-ticker sequential backfill** for 30m bars at startup: fetch multiple 31-bar slices sequentially per ticker until `max_ma_length` 30m bars are available, then aggregate to 1h and persist.
- Implement fast **minute snapshot** path that requests a single 31-bar 30m slice and merges/aggregates into hourly cache.
- Small win: run start-up and see cached parquet/ndjson files created and that `1h` cache contains enough bars for `200`-period MAs.

**Milestone 3 — Indicators & tables**

- File: `indicators.py`. Compute SMA/EMA durations and cache results.
- CLI: print per-ticker MA table showing distance to MAs.

**Milestone 4 — Minute updater**

- File: `updater.py`. Implement minute scheduler and data merging. CLI shows updated tables every minute.
- Small win: observe updates and printed messages.

**Milestone 5 — Hourly evaluator & logging**

- File: `signals.py`, `part_time_larry.py` (sample logger). Implement hourly evaluation and logging to `signals.log` (CSV/JSONL).
- Small win: At top of hour, generate signal and append to `signals.log` (dry-run).

**Milestone 6 — Order preparation & safety checks**

- File: `orders.py`. Prepare orders and implement final checks (re-fetch positions, compare sizes). In dry-run no submit. Add `--live` gate.
- Tests: mock IB and assert order prepared with exact size.

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

## 🔹 Implementation notes (development updates)

The current implementation includes the following developer-facing changes that affect runtime and testing:

- **Real IB client (ib_insync):** the CLI now uses `ib_insync` for live connections and historical requests. `ib_insync` must be installed in the runtime environment (e.g. `pip install ib_insync`). If IB is unreachable the connect call raises a descriptive error; we plan a configurable fallback for offline testing.

- **Regular Trading Hours (RTH) control:** historical requests accept a `useRTH` flag. The CLI exposes `--no-rth` to request full-session data; by default RTH is enabled (requests respect regular trading hours).

- **30m backfill target is hourly-based:** startup backfill requests 31-bar intraday slices sequentially per ticker until the configured **hourly** target is reached. The current default is **200 hourly bars** (i.e. ~400 half-hour bars). This is controlled by `target_hours` passed to the backfill routine.

- **Per-ticker sequential backfill:** to respect IB pacing rules, each ticker's multi-slice backfill runs in series; the downloader runs these sequences in controlled batches across tickers.

- **Launchers & CI helpers:** added lightweight launcher scripts `run_sellmanagement.ps1` and `run_sellmanagement.sh` for easy local runs with PYTHONPATH set correctly.

- **Tests:** unit tests were added for the backfill and 30m→1h aggregation logic. Continuous integration should run `pytest` against these tests.

These updates are already reflected in the code under `sell_manager_CLI/src/sellmanagement/` and in the example launch/usage notes earlier in this document.


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

## 🔎 Implementation audit vs code (auto-generated)

This section lists the PRD statements and whether they are implemented in the current codebase (as of this commit). For mismatches I note the file(s) and the suggested action.

- **Connect to IB on port 4001 and fetch positions/open orders**: Implemented. See `src/sellmanagement/__main__.py` (_cmd_start) using `IBClient` which calls `ib_insync.IB.connect()` in `src/sellmanagement/ib_client.py`. (OK)

- **Assigned MA CSV: `config/assigned_ma.csv` with columns `ticker,type,length,timeframe` and interactive prompts on missing rows**: Implemented. `src/sellmanagement/assign.py` and interactive flows in `src/sellmanagement/__main__.py` use `sync_assignments_to_positions` and `set_assignment`. Note: CSV header includes `timeframe` (code uses `timeframe`) — PRD header earlier omitted timeframe in some examples; update PRD to include timeframe column. (Minor doc update)

- **Download 1Y daily + 31D 30m and aggregate to hourly, sequential backfill per ticker, batch concurrency**: Mostly implemented. `src/sellmanagement/downloader.py` provides `batch_download_daily`, `_sequential_backfill_halfhours` and `persist_batch_halfhours` which perform sequential 31-bar slices and aggregation via `src/sellmanagement/aggregation.py`. Concurrency is implemented as batch processing (batch_size param) rather than an asyncio Semaphore; the implementation is synchronous with polite sleeps (OK but differs from async description). Action: Update PRD to reflect synchronous batch implementation and config knobs (`batch_size`, `batch_delay`) defined in `src/sellmanagement/config.py`.

- **Cache format and helpers**: Implemented as NDJSON under `config/cache/` with helpers in `src/sellmanagement/cache.py` using keys like `EXCHANGE__TICKER:1h` (OK). PRD recommended parquet/SQLite; code uses NDJSON. Update PRD to reflect NDJSON implementation.

- **Indicators (SMA/EMA for 5,10,20,50,100,150,200)**: Implemented in `src/sellmanagement/indicators.py` with `compute_sma_series_all` and `compute_ema_series_all`, plus enrichment helpers (OK).

- **Minute snapshot schedule: every minute fetch short durations and merge into cache**: Implemented by `run_minute_snapshot` in `src/sellmanagement/minute_snapshot.py` and the CLI's minute loop in `src/sellmanagement/__main__.py`. The PRD said fetch 7D daily + 1D hourly; code fetches `2 D` for daily-assigned tickers and `1 D` halfhour for hourly-assigned tickers. Update PRD to match implemented durations (`2 D` daily, `1 D` halfhours).

- **Signal evaluation at top-of-hour**: Implemented. `__main__.py` computes `is_top_of_hour` and calls `generate_signals_from_rows` in `src/sellmanagement/signal_generator.py`, which uses `last_close < ma_value` to decide SellSignal. Signals are logged with `src/sellmanagement/signals.py` into `logs/signals.jsonl`. (OK)

- **Signal logger / audit**: Implemented as JSONL `logs/signals.jsonl` in `src/sellmanagement/signals.py` and `signal_generator.append_signal` (OK). Note PRD suggested CSV/JSONL examples; code uses JSONL.

- **Order preparation & safety checks**: Core prepare→place pattern implemented and wired into the CLI with safety gating. `src/sellmanagement/orders.py` provides `prepare_close_order` and `execute_order` (dry-run by default). The IB wrapper `src/sellmanagement/ib_client.py` now includes `prepare_order` and `place_order` helpers that build IB contract/order objects and transmit via the existing `IB()` connection when available. The top-of-hour flow in `__main__.py` will, when `--live` is specified and the environment secret `SELLMANAGEMENT_LIVE_SECRET` is set and the user confirms, iterate SellSignal entries and call `prepare_close_order` → `execute_order`, which performs pre-submit checks (`positions()` and `openOrders()`) and calls into `IBClient.place_order` to transmit. Remaining work: idempotency tokens, coordinated cancels, position-size caps, retries and persistent audit. (Partial — core flow implemented)

- **CLI flags**: Implemented subset. `__main__.py` supports `--no-rth`, `--dry-run` (default True), `--live`, and `--client-id`. PRD listed `--config`, `--log-dir`, `--concurrency`, `--cache-dir` which are not implemented. Update PRD to match current flags and mark the others as future enhancements.

- **Tests**: Some unit tests exist for aggregation/backfill (per PRD note), but a full test suite is not present in the repository root. Mark tests as partial/ongoing. (TODO)

- **Other NFRs (reconnect/backoff, adaptive rate-limiter)**: Only basic polite sleeps and try/except traces are present; no adaptive rate limiter or reconnection manager. `IBClient.connect` raises on failure but no automatic reconnect loop exists. Mark these as remaining work.


## ✅ Quick code vs PRD summary (high-level)
- Implemented: IB connect + positions fetch, assigned-MA CSV and interactive assignment flow, NDJSON cache, downloader/backfill + aggregation, indicators, minute snapshot loop, signal generation and JSONL audit logging.
- Partially implemented / differs: concurrency model is batch/sleep-based (not full async semaphore), cache format NDJSON (PRD suggested parquet/SQLite), snapshot durations differ slightly (`2 D` daily vs PRD's 7D), CLI flags limited.
- Missing / TODO: live order placement adapters (`place_order`), strong safety gating for live mode, adaptive pacing/rate-limiter, reconnect manager, comprehensive CLI flags, and CI/test harness.


## Remaining implementation items (actionable)
- Finalize safety & idempotency for live transmits:
  - implement per-order idempotency tokens and persistent audit to avoid duplicate submits on restart/crash;
  - enforce position-size caps and a global daily limit to prevent runaway orders;
  - coordinate cancelation of other open orders for the same position as part of an atomic workflow. (High)
- Implement reconnect/backoff and a connection manager around `IBClient` to satisfy NFR1 (auto-retry, centralized reconnect policy, background bridge for async calls). (Medium)
- Add adaptive rate-limiter or token-bucket for historical requests (per-minute/hour buckets) instead of static sleeps to better respect IB pacing. (Medium)
- Add CLI flags: `--config`, `--log-dir`, `--concurrency`, `--cache-dir` and make `Config` respect them. (Low)
- Expand unit tests and CI configuration (pytest + mocks for `ib_insync`) and add explicit safety tests asserting `--dry-run` never calls `placeOrder()` in mocks. (High)
