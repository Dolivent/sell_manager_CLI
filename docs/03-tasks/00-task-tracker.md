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

## Active Tasks

| ID | Title | Status | Priority | Owner | Session | Details |
|----|-------|--------|----------|-------|---------|---------|
| T001 | Full codebase documentation restructure | IN_PROGRESS | P0 | — | S001 | [#](#T001) |

---

## Task Details

### T001 — Full codebase documentation restructure

**Status:** IN_PROGRESS  
**Priority:** P0  
**Created:** 2026-04-04  
**Session:** S001  
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
- [ ] Create `docs/04-bugs/00-bug-tracker.md`
- [ ] Create `docs/05-reference/` files
- [ ] Create `docs/06-user-guide/00-user-guide.md`
- [ ] Create `tmp/` README / marker file
- [ ] Verify all files render correctly

---

### T002 — Code review: extract interactive prompts from `__main__.py`

**Status:** OPEN  
**Priority:** P1  
**Created:** 2026-04-04  
**Session:** S001  
**Detail file:** [`docs/03-tasks/tracker/T002-extract-interactive-prompts.md`](tracker/T002-extract-interactive-prompts.md)

**Summary:**  
The `_cmd_start` function in `__main__.py` mixes CLI UI concerns (interactive ticker assignment prompts, `input()` calls) with business logic. Extract all interactive prompts into a dedicated `cli_prompts.py` module.

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

**Status:** OPEN  
**Priority:** P2  
**Created:** 2026-04-04  
**Session:** S001  
**Detail file:** [`docs/03-tasks/tracker/T005-proper-logging.md`](tracker/T005-proper-logging.md)

**Summary:**  
Replace the `trace.py` append-only approach with Python's `logging` module (with appropriate handlers for file + console output) and use structured log levels consistently.

---

## Completed Tasks

| ID | Title | Status | Completed |
|----|-------|--------|-----------|
| — | — | — | — |

---

## Blocked / Cancelled Tasks

| ID | Title | Status | Reason |
|----|-------|--------|--------|
| — | — | — | — |
