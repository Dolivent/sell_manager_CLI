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
| B001 | `__main__.py` is a 400+ line monolith | MEDIUM | OPEN | `__main__.py` | 2026-04-04 (S001) |
| B002 | `minute_snapshot.py` is a 400+ line monolith | MEDIUM | FIXED | `minute_snapshot.py` | 2026-04-04 (S001) |
| B003 | Re-entrant queue submission in `IBWorker._poll_positions` | MEDIUM | FIXED | `gui/ib_worker.py` | 2026-04-04 (S001) |
| B004 | `dry_run` flag handled inconsistently across `orders.py` and `order_manager.py` | MEDIUM | FIXED | `orders.py`, `order_manager.py` | 2026-04-04 (S001) |
| B005 | `assigned_ma.csv` has hardcoded `use_rth=False` default | LOW | OPEN | `assign.py` | 2026-04-04 (S001) |
| B006 | Position symbol normalisation mismatch in `widgets.py` vs `ib_worker.py` | MEDIUM | OPEN | `gui/widgets.py`, `gui/ib_worker.py` | 2026-04-04 (S001) |
| B007 | `assigned_ma.py` `use_rth` is always `False` — hardcoded | LOW | OPEN | `gui/assigned_ma.py` | 2026-04-04 (S001) |
| B008 | Missing `__pycache__` / `.pyc` patterns in `.gitignore` for nested dirs | LOW | FIXED | `.gitignore` | 2026-04-04 (S001) |
| B009 | `docs/` folder is gitignored — documentation not versioned | MEDIUM | FIXED | `.gitignore` | 2026-04-04 (S001) |
| B010 | `__pycache__` and `.egg-info` not cleaned by `scripts/clean_export.py` | LOW | OPEN | `scripts/clean_export.py` | 2026-04-04 (S001) |

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
**Status:** OPEN  
**Component:** `gui/assigned_ma.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04

**Summary:** The `AssignedMAStore` class initialises `use_rth = False` in its `__init__` and stores it as an instance attribute. This value is never exposed as a configurable setting and is hardcoded to `False`. Using regular trading hours only means the tool may miss data at the open/close auction if the user wants off-hours data included.

**Steps to reproduce:**
1. Inspect `gui/assigned_ma.py`

**Expected behavior:** `use_rth` should be configurable or at minimum documented.

**Actual behavior:** `use_rth` is always `False`.

**Root cause:** Design oversight — no UI control for this setting.

**Fix / Workaround:** Add `use_rth` to the SettingsWidget and persist via `settings_store.py`.

**Related tasks:** T001  
**Related sessions:** S001

---

## [B006] — Position symbol normalisation mismatch between widgets and ib_worker

**Severity:** MEDIUM  
**Status:** OPEN  
**Component:** `gui/widgets.py`, `gui/ib_worker.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04

**Summary:** `ib_worker.py` builds `symbol_full` as `f"{exchange}:{symbol}"` (e.g., `NASDAQ:AAPL`) but `widgets.py`'s `on_positions_update` does token matching with a mix of string suffix checks and exchange comparisons. This can cause positions to not update in the UI when the token format from IB differs from the format in `assigned_ma.csv`.

**Steps to reproduce:**
1. Connect to IB with a position
2. Observe that the PositionsWidget may not update qty/price for some tickers

**Expected behavior:** All live positions update in the PositionsWidget.

**Actual behavior:** Position update may be silently skipped for tickers where token format differs.

**Root cause:** Inconsistent token normalisation across modules. `widgets.py` uses `norm()` with suffix matching; `ib_worker.py` uses `exchange:symbol` format.

**Fix / Workaround:** Establish a single `normalise_ticker()` function used by both modules. Ensure `assigned_ma.csv` and IB token format are consistent.

**Related tasks:** T001  
**Related sessions:** S001

---

## [B005] — `assigned_ma.csv` hardcodes `use_rth=False` in assign module

**Severity:** LOW  
**Status:** OPEN  
**Component:** `assign.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04

**Summary:** `sync_assignments` and `sync_assignments_to_positions` accept `default_type`, `default_length`, `default_timeframe` parameters but not `use_rth`. The `use_rth` flag is not stored in the CSV and cannot be configured per-ticker.

**Steps to reproduce:**
1. Inspect `assign.py`

**Expected behavior:** `use_rth` should be configurable per assignment or at least globally.

**Actual behavior:** No `use_rth` configuration.

**Root cause:** Design gap — `use_rth` is a global setting in `ib_client.py` but not exposed in assignment storage.

**Fix / Workaround:** Add `use_rth` column to `assigned_ma.csv` and wire through `assign.py` and `ib_client.py`.

**Related tasks:** T001  
**Related sessions:** S001

---

## [B004] — `dry_run` flag handled inconsistently across `orders.py` and `order_manager.py`

**Severity:** MEDIUM  
**Status:** FIXED  
**Component:** `orders.py`, `order_manager.py`  
**Discovered:** 2026-04-04 (session S001)  
**Last Updated:** 2026-04-04 (session S002)

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

**Session fixed:** S002

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
**Status:** OPEN  
**Component:** `__main__.py`  
**Discovered:** 2026-04-04 (S001)  
**Last Updated:** 2026-04-04

**Summary:** `_cmd_start` in `__main__.py` is approximately 400 lines. It mixes IB connection logic, live position fetching, assignment CSV management, interactive assignment prompts, minute loop scheduling, snapshot execution, signal generation, order preparation, order execution, and terminal output formatting — all in one function.

**Steps to reproduce:**
1. Open `__main__.py`
2. Count lines in `_cmd_start`

**Expected behavior:** `_cmd_start` should delegate to focused modules; interactive prompts should be in a separate `cli_prompts.py`.

**Actual behavior:** One large function handling many concerns.

**Root cause:** The CLI was built as a monolithic script before the GUI existed. Responsibilities were never split.

**Fix / Workaround:** Extract interactive assignment prompts into `cli_prompts.py`. Extract order execution logic into a `cli_executor.py`. Keep `_cmd_start` as the orchestration layer.

**Related tasks:** T002 (dedicated task for this)  
**Related sessions:** S001
