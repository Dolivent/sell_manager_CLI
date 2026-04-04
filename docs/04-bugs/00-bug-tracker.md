# Bug Tracker — Summary Index

> **Purpose:** Log every bug, design issue, regression suspicion, and known limitation.  
> **Rule:** Never delete entries. Closed bugs stay in the log as regression history.  
> **Format:** Newest entries first.

---

## How to Use

Add a new entry for every bug, regression, or design problem you encounter or identify:

```markdown
## [B###] — Title

**Severity:** CRITICAL / HIGH / MEDIUM / LOW / NOTE  
**Status:** OPEN / IN_PROGRESS / WORKAROUND / FIXED / WONTFIX / DUPLICATE  
**Component:** <module or area>  
**Discovered:** YYYY-MM-DD (session S###)  
**Last Updated:** YYYY-MM-DD

**Summary:** One-line description.

**Steps to reproduce:**
1. ...
2. ...

**Expected behavior:** ...
**Actual behavior:** ...

**Root cause (if known):** ...

**Fix / Workaround:** ...

**Related tasks:** T###  
**Related sessions:** S###
```

---

## Bug Summary Table

| ID | Title | Severity | Status | Component | Discovered |
|----|-------|----------|--------|-----------|------------|
| B001 | `__main__.py` is a 400+ line monolith | MEDIUM | FIXED | `__main__.py`, `cli_prompts.py`, `cli_executor.py` | 2026-04-04 (S001) |
| B002 | `minute_snapshot.py` is a 400+ line monolith | MEDIUM | FIXED | `minute_snapshot.py` | 2026-04-04 (S001) |
| B003 | Re-entrant queue submission in `IBWorker._poll_positions` | MEDIUM | FIXED | `gui/ib_worker.py` | 2026-04-04 (S001) |
| B004 | `dry_run` flag handled inconsistently across `orders.py` and `order_manager.py` | MEDIUM | FIXED | `orders.py`, `order_manager.py` | 2026-04-04 (S001) |
| B005 | `assigned_ma.csv` has hardcoded `use_rth=False` default | LOW | FIXED | `assign.py` | 2026-04-04 (S001) |
| B006 | Position symbol normalisation mismatch in `widgets.py` vs `ib_worker.py` | MEDIUM | FIXED | `gui/widgets.py`, `gui/ib_worker.py`, `utils/ticker.py` | 2026-04-04 (S001) |
| B007 | `assigned_ma.py` `use_rth` is always `False` — hardcoded | LOW | FIXED | `gui/assigned_ma.py` | 2026-04-04 (S001) |
| B008 | Missing `__pycache__` / `.pyc` patterns in `.gitignore` for nested dirs | LOW | FIXED | `.gitignore` | 2026-04-04 (S001) |
| B009 | `docs/` folder is gitignored — documentation not versioned | MEDIUM | FIXED | `.gitignore` | 2026-04-04 (S001) |
| B010 | `__pycache__` and `.egg-info` not cleaned by `scripts/clean_export.py` | LOW | FIXED | `scripts/clean_export.py` | 2026-04-04 (S001) |

---

## Bug Details

<!-- Add bug entries below. Most recent first. -->

---

## [B010] — `clean_export.py` doesn't ignore `__pycache__` and `.egg-info`

**Severity:** LOW  
**Status:** FIXED  
**Component:** `scripts/clean_export.py`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** `scripts/clean_export.py` used `shutil.ignore_patterns('.git', 'logs', 'config/cache', '__pycache__')` which ignores only `__pycache__` at the root. Nested `__pycache__` dirs inside packages and `.egg-info/` were not excluded.

**Root cause:** `shutil.ignore_patterns` requires globstar patterns for recursive matching.

**Fix / Workaround:** Added `'**/__pycache__'`, `'**/*.pyc'`, `'**/*.egg-info'` to ignore patterns. Also updated the generated `.gitignore` in the export to include the same patterns.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B009] — `docs/` folder is gitignored — documentation not versioned

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `.gitignore`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** The entire `docs/` directory was listed in `.gitignore`, meaning the documentation structure and content were not tracked in version control.

**Root cause:** `.gitignore` had `docs/` on its own line. Note that `docs/PRD_sell_manager_CLI.md` is already listed separately at the top of `.gitignore` (a proprietary document that should not be versioned), so `docs/` can be safely removed.

**Fix / Workaround:**
- Removed `docs/` from `.gitignore`.
- `docs/PRD_sell_manager_CLI.md` remains ignored (it's a proprietary internal document listed separately at line 62).
- Documentation is now versioned alongside the code.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B008] — Missing `__pycache__` / `.pyc` patterns in `.gitignore` for nested dirs

**Severity:** LOW  
**Status:** FIXED  
**Component:** `.gitignore`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** The `.gitignore` had `__pycache__/` (root-level) and `*.pyc` but did not use globstar patterns (`**/__pycache__/`, `**/*.pyc`) to cover nested `__pycache__` directories inside packages.

**Root cause:** Pattern `__pycache__/` matches only at root level.

**Fix / Workaround:** Added `**/__pycache__/` and `**/*.pyc` patterns to `.gitignore`.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B007] — `assigned_ma.py` `use_rth` is always `False` — hardcoded

**Severity:** LOW  
**Status:** FIXED  
**Component:** `gui/assigned_ma.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** The `AssignedMAStore` class had no `use_rth` concept (it was `False` in GUI). Combined fix with B005.

**Fix / Workaround:** See B005.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B006] — Position symbol normalisation mismatch between widgets and ib_worker

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `gui/widgets.py`, `gui/ib_worker.py`, `utils/ticker.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** `ib_worker.py` built `symbol_full` as `f"{exchange}:{symbol}"` (e.g. `NASDAQ:AAPL`) but `widgets.py`'s `on_positions_update` used a local `norm()` function with mixed string suffix checks. This caused positions to not update in the UI when token formats differed.

**Root cause:** Inconsistent token normalisation across modules.

**Fix / Workaround:**
- Created `utils/ticker.py` with `normalise_ticker()`, `ticker_to_symbol()`, and `tickers_match()`.
- `widgets.py` now imports and uses `tickers_match()` for position matching, replacing the local `norm()` closure.
- `ib_worker.py` imports `tickers_match` for future consistency.
- Both modules now share the same ticker comparison logic.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B005] — `assigned_ma.csv` hardcodes `use_rth=False` in assign module

**Severity:** LOW  
**Status:** FIXED  
**Component:** `gui/settings_store.py`, `gui/widgets.py`, `gui/ib_worker.py`, `gui/main_window.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** `sync_assignments` and `sync_assignments_to_positions` accept `default_type`, `default_length`, `default_timeframe` parameters but not `use_rth`. The `use_rth` flag was not stored and was always `True` in CLI but `False` in GUI. `AssignedMAStore` also hardcoded `use_rth = False`.

**Root cause:** Design gap — `use_rth` is a global IB setting but was not exposed as configurable.

**Fix / Workaround:**
- Added `get_use_rth()` / `set_use_rth()` to `gui/settings_store.py`, persisting the flag via Qt QSettings (registry on Windows).
- Added "Use regular trading hours only (RTH)" checkbox to `SettingsWidget` in `widgets.py`, loaded from persisted settings on startup.
- `IBWorker.connect()` now accepts `use_rth` parameter and passes it to `IBClient`.
- `main_window.py` reads `use_rth` from `settings_tab.use_rth` property when initiating connections.
- `_schedule_reconnect` preserves the `use_rth` value across reconnects.
- B005 and B007 are resolved as a combined fix: `use_rth` is now a globally configurable setting persisted across sessions.

**Session fixed:** S002

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B004] — `dry_run` flag handled inconsistently across `orders.py` and `order_manager.py`

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `orders.py`, `order_manager.py`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S003)

**Summary:** `orders.py`'s `execute_order` accepts `dry_run: bool = True` and checks it at multiple points. `order_manager.py`'s `place_and_finalize` had no `dry_run` parameter — it always attempted live transmission. If `order_manager.place_and_finalize` was called directly, no dry-run protection existed.

**Steps to reproduce:**
1. Call `order_manager.place_and_finalize` directly with a prepared IB order
2. Observe that orders are transmitted live with no dry-run check

**Expected behavior:** All order transmission routes respect a dry-run flag.

**Actual behavior:** `order_manager.place_and_finalize` always attempted live transmission.

**Root cause:** `dry_run` parameter existed in `orders.py` but `order_manager.py` was written as a live-only module, and the parameter was not passed through.

**Fix / Workaround:**
- Added `dry_run: bool = False` parameter to `order_manager.place_and_finalize`. When `True`, returns a simulated result dict without placing any live order.
- Updated `orders.execute_order` to pass `dry_run=dry_run` to `order_manager.place_and_finalize`.
- Added `'dry_run': False` to the live path result dict.
- **S003:** Repaired a syntax regression in `orders.py` (orphan `try:` without `except`/`finally` around the live position cap block) that prevented the module from loading.

**Session fixed:** S002 (logic); S003 (syntax regression)

**Related tasks:** T001  
**Related sessions:** S001, S002

---

## [B003] — Re-entrant queue submission in `IBWorker._poll_positions`

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `gui/ib_worker.py`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** When `_poll_positions` encountered 3+ consecutive errors, it called `self.connect(...)` via `_submit_to_ib_thread`, submitting reconnect work back into the same queue (re-entrant). Additionally, `connect`'s own reconnect path used `threading.Timer` that also called `_submit_to_ib_thread`.

**Steps to reproduce:**
1. Simulate 3 consecutive position poll failures
2. Observe reconnect submission into the same queue

**Expected behavior:** Reconnect should be handled outside the IB thread queue.

**Actual behavior:** Reconnect task queued for the same IB thread.

**Root cause:** No separation between "work" queue and "control" operations (connect/disconnect). Both `_poll_positions` error handler and `connect`'s own reconnect path submitted back to `_submit_to_ib_thread`.

**Fix / Workaround:**
- Added `_schedule_reconnect(host, port, client_id)` method that runs `connect()` on a short-lived daemon `threading.Thread`, bypassing the IB queue entirely.
- Changed `_poll_positions` error handler (≥3 errors) to call `_schedule_reconnect` instead of `_submit_to_ib_thread`.
- Changed `connect`'s own reconnect path (on connection failure) to also use `_schedule_reconnect` instead of `_submit_to_ib_thread`.
- This ensures reconnect never blocks or delays other queued work, and never creates re-entrant queue submissions.

**Session fixed:** S002

**Related tasks:** T004  
**Related sessions:** S001, S002

---

## [B002] — `minute_snapshot.py` is a 400+ line monolith

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `minute_snapshot.py`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

**Summary:** `run_minute_snapshot` was a ~570-line function handling IB data downloading, 30m→1h aggregation, freshness detection, stale backfill, MA computation, snapshot row construction, and JSONL logging — all in one function.

**Root cause:** Organic growth — features added incrementally without refactoring.

**Fix / Workaround:**
- Created `SnapshotRow` dataclass to represent each per-ticker row (replaces flat dict construction).
- Created `SnapshotContext` dataclass to carry intermediate state cleanly across phases.
- Extracted four focused sub-functions per T003 design:
  - `_build_context()`: fetches live positions/orders, builds position maps, partitions tickers by timeframe
  - `_fetch_and_cache()`: batch-downloads daily bars, iterates hourly tickers calling `_fetch_hourly_for_ticker`
  - `_compute_snapshot_rows()`: iterates tickers, computes MA, last_close, abv_be, returns `List[SnapshotRow]`
  - `_write_snapshot_log()`: appends JSONL entry
- Helper sub-functions: `_partition_tickers`, `_build_position_maps`, `_build_orders_map`, `_fetch_hourly_for_ticker`, `_required_halfhour_bars`, `_download_halfhours`, `_backfill_if_insufficient`, `_check_freshness`, `_backfill_stale`, `_compute_single_row`, `_load_bars_for_ticker`, `_extract_closes`, `_compute_last_close_and_bar`, `_compute_ma_and_distance`.
- `run_minute_snapshot` now orchestrates: `_build_context → _fetch_and_cache → _compute_snapshot_rows → _write_snapshot_log`.
- File reduced from ~570 lines to ~470 lines. Each sub-function has a clear single responsibility.

**Session fixed:** S002

**Related tasks:** T003  
**Related sessions:** S001, S002

---

## [B001] — `__main__.py` is a 400+ line monolith

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `__main__.py`, `cli_prompts.py`, `cli_executor.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04 (S004)

**Summary:** `_cmd_start` in `__main__.py` is approximately 400 lines. It mixes IB connection logic, live position fetching, assignment CSV management, interactive assignment prompts, minute loop scheduling, snapshot execution, signal generation, order preparation, order execution, and terminal output formatting — all in one function.

**Steps to reproduce:**
1. Open `__main__.py`
2. Count lines in `_cmd_start`

**Expected behavior:** `_cmd_start` should delegate to focused modules; interactive prompts should be in a separate `cli_prompts.py`.

**Actual behavior (before fix):** One large function handling many concerns.

**Root cause:** The CLI was built as a monolithic script before the GUI existed. Responsibilities were never split.

**Fix / Workaround (S004):**
- Added `cli_prompts.py`: MA assignment menu (`prompt_ma_assignment`, `build_ma_assignment_options`, `read_ma_selection`, etc.) and `confirm_live_transmit(assume_yes=...)` for live YES gating.
- Added `cli_executor.py`: `transmit_live_sell_signals(ib, generated, snapshot_ts=...)` for the live SellSignal transmit path (intent idempotency, qty cap, `execute_order`).
- `_cmd_start` now calls these modules; startup and runtime assignment flows both use `prompt_ma_assignment`.
- CLI flag `--yes-to-all` (with `--live`) skips the interactive confirmation for scripted runs.
- `_cmd_start` remains the orchestration shell (minute loop, sync, snapshot table printing); further splits (e.g. table formatting) are optional.

**Note (S003):** A corrupted f-string in the live-order position cap loop was repaired (SyntaxError).

**Session fixed:** S004

**Related tasks:** T002  
**Related sessions:** S001, S003, S004
