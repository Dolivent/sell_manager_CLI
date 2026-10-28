# Refactor Audit — sellmanagement CLI

This audit inspects the current implementation in `sell_manager_CLI/src/sellmanagement/` against the PRD and common quality targets (readability, testability, single-responsibility, maintainability). It highlights inefficiencies, duplicated patterns, deeply nested logic, and provides prioritized refactor suggestions.

Overview
- Files inspected: `__main__.py`, `ib_client.py`, `downloader.py`, `aggregation.py`, `cache.py`, `minute_snapshot.py`, `assign.py`, `indicators.py`, `signals.py`, `signal_generator.py`, `orders.py`.
- Goal: produce actionable refactors with clear priorities so we can incrementally clean the codebase.


Findings (by file)

- `src/sellmanagement/__main__.py`
  - Large function `_cmd_start` (~300+ lines): performs many responsibilities (config setup, IB connect, assignment sync, interactive prompting, backfill initiation, long-running minute loop, signal triggering, CLI printing). This violates SRP and makes testing hard.
  - Deep nesting and repeated try/except blocks make control flow hard to follow. Example: nested try/except inside the minute loop performing position refresh → sync → prompt → snapshot → signal eval → printing. Hard to unit-test or stub individual steps.
  - Interactive prompting logic duplicated between startup and runtime snapshot flows. Extracting to a helper reduces duplication.
  - Use of `getattr(..., None) or getattr(..., None)` appears redundant in a few places and should be simplified.
  - Hard-coded timezone `America/New_York` sprinkled through the file; centralize timezone handling.
  - CLI argument parsing defines `--dry-run` default True and also `--live`, causing potential confusion: `Config(dry_run=not getattr(args, 'live', False)` — but `--dry-run` is parsed and ignored. Simplify flag semantics.

- `src/sellmanagement/ib_client.py`
  - `IBClient.connect` raises RuntimeError on failure; no reconnect/backoff logic exists. Consider a connection manager wrapper.
  - The class exposes download/positions/openOrders but lacks `place_order`/`cancel_order` adapters expected by `orders.py`. This mismatch creates a manual integration gap.
  - The code duplicates date-to-IB-format logic in `download_halfhours` that could be shared with other modules.
  - The class is synchronous and tightly coupled to `ib_insync.IB` — wrap external dependency behind a smaller protocol interface for easier mocking.

- `src/sellmanagement/downloader.py`
  - Mixes synchronous sleeps and batch logic as a pacing mechanism; this is acceptable but not consistent with PRD's async semaphore description.
  - `_sequential_backfill_halfhours` and `persist_batch_halfhours` implement similar iterative slice logic; consider consolidating into a single reusable backfill iterator to avoid duplication.
  - `_chunks` helper duplicated pattern; could be moved to a small util module.

- `src/sellmanagement/minute_snapshot.py`
  - `run_minute_snapshot` is fairly long and performs multiple responsibilities: partition tickers, download daily/halfhours, merge caches, compute MA, choose candidate bars, and build rows. Break into helper functions: partition_tickers, fetch_daily_for_tickers, fetch_halfhours_and_aggregate, choose_last_bar, compute_row.
  - Bar selection logic (candidates/last_bar) has nested try/except and repeated parsing; consolidate into a small utility and add unit tests for corner cases (pre-market, missing tzinfo, non-ISO dates).
  - `assignments` mapping uses raw ticker keys; some functions use uppercase matching elsewhere; normalize keys consistently (either canonical uppercase or preserve original tokens with separate lookup keys).

- `src/sellmanagement/cache.py`
  - Uses NDJSON append-all writes. Merge logic loads entire file, builds dict, and rewrites; performance may degrade with large files. Consider switching to append-with-index (sqlite or parquet) or at least limiting memory usage and using streaming merges.
  - `_key_to_path` uses simple replacement; consider ensuring uniqueness and safe characters across OSes.

- `src/sellmanagement/indicators.py`
  - Well-contained and testable; minor micro-optimizations possible (numpy vectorization) but unnecessary unless perf bottleneck found.

- `src/sellmanagement/assign.py`
  - Duplicated CSV read/write patterns across functions. Consolidate CSV load/save helpers.
  - `sync_assignments_to_positions` writes blank assignment rows for new tokens; interactive prompting relies on exact string equality; consider canonicalization (strip/uppercase) consistently for both file and IB tokens.

- `src/sellmanagement/signal_generator.py` & `signals.py`
  - Signal generation is small and clean; `append_signal` writes JSONL without structured schema enforcement. Add a typed dataclass or schema validator and a small helper to sanitize inputs.

- `src/sellmanagement/orders.py`
  - Minimal implementation but `execute_order` expects an `ib_client.place_order` that doesn't exist. Also the `PreparedOrder.details` contains TODOs. Implement a clearer prepared-order schema and adapter functions to convert to IB-specific order objects.


Cross-cutting issues

- Lack of a central orchestrator/service class: currently `__main__` acts as both CLI and runtime orchestrator. Introduce `ServiceOrchestrator` that composes `IBClient`, `Downloader`, `Cache`, `Snapshotter`, `SignalGenerator`, and `OrderManager` with clear lifecycle methods (start/stop/reconnect). This will dramatically simplify `__main__` and improve testability.

- Trace/logging usage is ad-hoc via `append_trace`; prefer standard `logging` for operational logs plus JSONL for audits. Keep `append_trace` for lightweight traces but centralize log paths via `Config`.

- Timezone handling: multiple modules assume `America/New_York`. Centralize timezone and provide helpers to convert to IB's expected formats.

- Concurrency model inconsistency: PRD expects async semaphore; code uses synchronous batch + sleeps. Decide on a concurrency model and standardize across downloader & snapshotter; a small `DownloadController` can provide semaphore or process-pool abstraction.


Prioritized refactor suggestions (actionable)

1) High priority — Extract orchestrator and thin CLI
   - Create `src/sellmanagement/orchestrator.py` with a `SellManagementService` class (start/stop/reconnect). Move the minute loop and startup/backfill sequencing into this class. Keep CLI responsible only for arg parsing and invoking the service. Benefits: reduces `_cmd_start` size, testable lifecycle, central reconnect/backoff.

2) High priority — Orders integration & safety
   - Add `IBClient.place_order` and `IBClient.cancel_order` adapters and implement an `OrderManager` that performs pre-checks (re-fetch positions, size caps, idempotency token) and calls `orders.execute_order`. Add unit tests that assert dry-run never calls `place_order`.

3) High priority — Break up `__main__` and `run_minute_snapshot`
   - Split `__main__._cmd_start` into smaller functions; extract prompt logic into `assign_prompt.py` and snapshot row building into `snapshot_builder.py`.

4) Medium — Standardize cache and migration path
   - Replace NDJSON merge logic with a lightweight SQLite table or add an optional `cache_backend` abstraction so large caches are manageable. If immediate migration is heavy, add streaming merge (do not load entire files when merging large slices), and add file rotation.

5) Medium — Consolidate backfill logic
   - Merge `_sequential_backfill_halfhours` and `persist_batch_halfhours` into a single backfill iterator/generator, remove duplication, and expose progress hooks.

6) Medium — Normalize assignments & tokens
   - Centralize token normalization (uppercase exchange + symbol) and ensure `assign` reads/writes use the same canonical form.

7) Low — Logging, config flags, and CLI parity with PRD
   - Add missing CLI flags (`--config`, `--log-dir`, `--concurrency`, `--cache-dir`), make `Config` load from file/env, and centralize logging config.

8) Low — Optional performance: vectorize indicators
   - If profiling shows indicator calc is bottleneck, rewrite `indicators.py` to use numpy or pandas for faster series computation.


Concrete small refactor steps to start (safe, low-risk)
- Extract `assign_prompt` helper from `__main__.py` (move duplicated prompt code into `assign.py` or new `assign_prompt.py`).
- Extract small helpers from `minute_snapshot.py`:
  - `partition_tickers_by_timeframe(assignments, tickers)`
  - `select_latest_bar_before_snapshot(bars, snapshot_ts)`
- Add `IBClient.place_order` stub that raises NotImplementedError and update `orders.execute_order` to call `ib_client.place_order` when not dry-run; this makes the missing contract explicit and testable.


Files to add for refactor scaffolding
- `src/sellmanagement/orchestrator.py` (service lifecycle)
- `src/sellmanagement/order_manager.py` (safety checks + call to `orders.py`)
- `src/sellmanagement/assign_prompt.py` (interactive and non-interactive assignment helpers)


Next steps I can take for you
- Create the scaffold edits for `orchestrator.py`, `order_manager.py`, and `assign_prompt.py` and move the related code out of `__main__.py` into them. (I can implement these changes incrementally and run linter checks.)
- Implement `IBClient.place_order` adapter and update `orders.execute_order` to use it in live mode, plus unit tests to prevent live sends in dry-run.

Choose one of the next steps above and I will implement it, keeping edits small and testable.
