# Task Tracker — Summary Index

> **Purpose:** High-level task index. Links to expanded detail files in `docs/03-tasks/tracker/`.  
> **Rule:** Never put full task context here. Use the tracker files. Update status in both places.

---

## How to Use

| Tag | Meaning |
|-----|---------|
| `OPEN` | Not yet started |
| `IN_PROGRESS` | Actively being worked |
| `IN_REVIEW` | Work complete, awaiting review |
| `BLOCKED` | Cannot proceed — dependency or external blocker |
| `DONE` | Completed and verified |
| `CANCELLED` | Abandoned (with reason) |

| Priority | Meaning |
|---------|---------|
| `P0` | Critical — blocks all other work |
| `P1` | High — should be addressed soon |
| `P2` | Medium — planned but not urgent |
| `P3` | Low — nice to have |

---

## Backlog Summary (T006–T016)

| ID | Title | Status | Priority | Detail |
|----|-------|--------|----------|--------|
| T006 | CI pipeline | DONE | P2 | [T006](tracker/T006-ci-pipeline.md) |
| T007 | Logging phase 2 (console + module loggers) | DONE | P2 | [T007](tracker/T007-logging-phase2.md) |
| T008 | Further `_cmd_start` decomposition | DONE | P2 | [T008](tracker/T008-cmd-start-splits.md) |
| T009 | IBWorker unit tests | DONE | P2 | [T009](tracker/T009-ibworker-tests.md) |
| T010 | Trace / `append_trace` tests | DONE | P3 | [T010](tracker/T010-trace-tests.md) |
| T011 | `cli_executor` unit tests | DONE | P3 | [T011](tracker/T011-cli-executor-tests.md) |
| T012 | Pytest + dev tooling | DONE | P3 | [T012](tracker/T012-pytest-dev.md) |
| T013 | Runbook / ops hardening | DONE | P3 | [T013](tracker/T013-runbook-ops.md) |
| T014 | GUI smoke checklist | DONE | P3 | [T014](tracker/T014-gui-smoke.md) |
| T015 | Product backlog bucket | OPEN | P3 | [T015](tracker/T015-product-backlog.md) — living list of future features |
| T016 | Trace rotation via env (`SELLMANAGEMENT_TRACE_*`) | DONE | P3 | [T016](tracker/T016-trace-rotation-env.md) — from T015 |

## Active Tasks

**T015** remains an **OPEN** parking lot for unprioritised product ideas (see tracker file). **T016** (trace rotation env) is **DONE** (session S008). T006–T014 remain **DONE** (session S007).

---

## Task Details

### T001 — Full codebase documentation restructure

**Status:** DONE  
**Priority:** P0  
**Created:** 2026-04-04  
**Session completed:** S002  
**Detail file:** [`docs/03-tasks/tracker/T001-full-docs-restyle.md`](tracker/T001-full-docs-restyle.md)

**Summary:**  
Review the entire codebase, redesign the `docs/` folder structure with numbered prefixes, create architecture documentation, a session tracker, a task tracker with two-level design (summary + expanded detail), a bugs/problems tracker, reference docs, and a user guide. Create a `tmp/` folder for temporary working scripts.

**Progress:**
- [x] Explore codebase structure
- [x] Read all existing docs
- [x] Design and create new docs folder structure
- [x] Create `docs/00-project/00-readme.md`
- [x] Create `docs/00-project/01-charter.md`
- [x] Create `docs/01-architecture/00-architecture-overview.md`
- [x] Create `docs/02-sessions/00-session-tracker.md` with S001 entry
- [x] Create `docs/03-tasks/00-task-tracker.md` (this file)
- [x] Create `docs/03-tasks/tracker/T001-*.md`
- [x] Create `docs/04-bugs/00-bug-tracker.md`
- [x] Create `docs/05-reference/` files
- [x] Create `docs/06-user-guide/00-user-guide.md`
- [x] Create `tmp/` README / marker file
- [x] Verify structure (ongoing spot-checks per session)

---

### T002 — Code review: extract interactive prompts from `__main__.py`

**Status:** DONE  
**Priority:** P1  
**Created:** 2026-04-04  
**Session completed:** S004  
**Detail file:** [`docs/03-tasks/tracker/T002-extract-interactive-prompts.md`](tracker/T002-extract-interactive-prompts.md)

**Summary:**  
The `_cmd_start` function in `__main__.py` mixes CLI UI concerns (interactive ticker assignment prompts, `input()` calls) with business logic. Extract all interactive prompts into a dedicated `cli_prompts.py` module.

**Resolution (S004):**  
`cli_prompts.py` + `cli_executor.py`; `--yes-to-all`; `tests/test_cli_prompts.py`. Bug B001 FIXED.

---

### T003 — Code review: extract snapshot logic from `minute_snapshot.py`

**Status:** DONE  
**Priority:** P1  
**Created:** 2026-04-04  
**Session:** S001  
**Session completed:** S002  
**Detail file:** [`docs/03-tasks/tracker/T003-extract-snapshot-logic.md`](tracker/T003-extract-snapshot-logic.md)

**Summary:**  
`minute_snapshot.py`'s `run_minute_snapshot` function is over 350 lines and handles data downloading, aggregation, freshness detection, backfill, MA computation, and logging all in one function. Break it into focused sub-functions.

**Resolution (S002):**
- Created `SnapshotRow` and `SnapshotContext` dataclasses.
- Extracted 4 phases: `_build_context`, `_fetch_and_cache`, `_compute_snapshot_rows`, `_write_snapshot_log`.
- Bug B002 marked FIXED.

---

### T004 — Code review: reconnect loop in `ib_worker.py`

**Status:** DONE  
**Priority:** P1  
**Created:** 2026-04-04  
**Session:** S001  
**Session completed:** S002  
**Detail file:** [`docs/03-tasks/tracker/T004-ib-worker-reconnect.md`](tracker/T004-ib-worker-reconnect.md)

**Summary:**  
The `_poll_positions` method submits a reconnect call back into `_submit_to_ib_thread` when consecutive errors exceed threshold. This creates a re-entrant queue submission pattern that should be reviewed and potentially simplified.

**Resolution (S002):**
- Added `_schedule_reconnect()` method that runs `connect()` on a dedicated daemon thread, bypassing the IB queue entirely.
- Both the `_poll_positions` error handler and `connect`'s own reconnect path now use `_schedule_reconnect()`.
- Bug B003 marked FIXED.

---

### T005 — Implement proper logging instead of `trace.py` prints

**Status:** DONE (phase 1)  
**Priority:** P2  
**Created:** 2026-04-04  
**Session completed:** S004  
**Detail file:** [`docs/03-tasks/tracker/T005-proper-logging.md`](tracker/T005-proper-logging.md)

**Summary:**  
Replace the `trace.py` append-only approach with Python's `logging` module (with appropriate handlers for file + console output) and use structured log levels consistently.

**Resolution (S004):**  
`append_trace` uses `RotatingFileHandler` (same JSON lines and path). Console levels and per-module `logging` migration deferred.

---

### T006 — CI pipeline

**Status:** DONE  
**Priority:** P2  
**Session completed:** S006  
**Detail file:** [`docs/03-tasks/tracker/T006-ci-pipeline.md`](tracker/T006-ci-pipeline.md)

**Summary:** GitHub Actions: `pip install -e ".[gui]"`, `compileall`, `unittest`, then `pytest` + `QT_QPA_PLATFORM=offscreen`. Matrix Python 3.10–3.12.

---

### T007 — Logging phase 2

**Status:** DONE | **Session:** S007 | **Detail:** [`T007-logging-phase2.md`](tracker/T007-logging-phase2.md)  
**Resolution:** `log_config.setup_logging()` on CLI + GUI entry; stderr WARNING+ for `sellmanagement.*`; `downloader` logs backfill errors; `append_trace` logs failures at WARNING.

### T008 — Further `_cmd_start` splits

**Status:** DONE | **Session:** S007 | **Detail:** [`T008-cmd-start-splits.md`](tracker/T008-cmd-start-splits.md)  
**Resolution:** `cli_loop.py` — minute sleep, heartbeat/gap, signal batch preview, snapshot sort/print.

### T009 — IBWorker tests

**Status:** DONE | **Session:** S007 | **Detail:** [`T009-ibworker-tests.md`](tracker/T009-ibworker-tests.md)  
**Resolution:** `tests/test_ib_worker.py` (reconnect after 3 errors, counter reset). **Bugfix:** `IBWorker.connect` reconnect timer used undefined `h,p,cid` → fixed to `host,port,client_id`.

### T010 — Trace tests

**Status:** DONE | **Session:** S007 | **Detail:** [`T010-trace-tests.md`](tracker/T010-trace-tests.md)  
**Resolution:** `tests/test_trace.py` with temp log path and handler cleanup (Windows-safe).

### T011 — `cli_executor` tests

**Status:** DONE | **Session:** S007 | **Detail:** [`T011-cli-executor-tests.md`](tracker/T011-cli-executor-tests.md)  
**Resolution:** `tests/test_cli_executor.py`.

### T012 — Pytest / dev tooling

**Status:** DONE | **Session:** S007 | **Detail:** [`T012-pytest-dev.md`](tracker/T012-pytest-dev.md)  
**Resolution:** CI runs `pytest tests -q` after `unittest`.

### T013 — Runbook ops

**Status:** DONE | **Session:** S007 | **Detail:** [`T013-runbook-ops.md`](tracker/T013-runbook-ops.md)  
**Resolution:** Runbook §2a.1 client IDs, `--yes-to-all`, trace rotation, Gateway readiness.

### T014 — GUI smoke

**Status:** DONE | **Session:** S007 | **Detail:** [`T014-gui-smoke.md`](tracker/T014-gui-smoke.md)  
**Resolution:** `docs/06-user-guide/02-gui-smoke.md` checklist.

### T015 — Product backlog

**Status:** OPEN | **Priority:** P3 | **Detail:** [`T015-product-backlog.md`](tracker/T015-product-backlog.md)

### T016 — Trace log rotation (environment)

**Status:** DONE | **Session:** S008 | **Detail:** [`T016-trace-rotation-env.md`](tracker/T016-trace-rotation-env.md)  
**Resolution:** `SELLMANAGEMENT_TRACE_MAX_MB`, `SELLMANAGEMENT_TRACE_BACKUPS`; runbook + API + tests.

---

## Completed Tasks

| ID | Title | Status | Completed |
|----|-------|--------|-----------|
| T001 | Full codebase documentation restructure | DONE | S002 |
| T002 | Extract interactive prompts from `__main__.py` | DONE | S004 |
| T003 | Extract snapshot logic from `minute_snapshot.py` | DONE | S002 |
| T004 | Reconnect loop in `ib_worker.py` | DONE | S002 |
| T005 | Proper logging instead of `trace.py` (phase 1) | DONE | S004 |
| T006 | CI pipeline | DONE | S006 |
| T007 | Logging phase 2 | DONE | S007 |
| T008 | `_cmd_start` / CLI loop splits | DONE | S007 |
| T009 | IBWorker unit tests | DONE | S007 |
| T010 | Trace tests | DONE | S007 |
| T011 | cli_executor tests | DONE | S007 |
| T012 | Pytest in CI | DONE | S007 |
| T013 | Runbook ops | DONE | S007 |
| T014 | GUI smoke doc | DONE | S007 |
| T016 | Trace rotation env vars | DONE | S008 |

---

## Blocked / Cancelled Tasks

| ID | Title | Status | Reason |
|----|-------|--------|--------|
| — | — | — | — |
