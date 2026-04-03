# Session Tracker

> **Purpose:** Mandatory session log. Every work session must add an entry here.  
> This is the project's primary defence against context drift.  
> **Format:** Newest entry first.

---

## How to Use

At the start of each session, add a new entry:

```markdown
## [YYYY-MM-DD] — Session #[N]

**Goal:** <what you intend to accomplish>
**Started:** HH:MM | **Ended:** HH:MM | **Outcome:** SUCCESS / PARTIAL / BLOCKED

**Context restored from:** <link to previous session or tracker entry>
**Decisions made:**
- <decision 1>
- <decision 2>
**New information learned:**
- <finding 1>
- <finding 2>
**Problems encountered:**
- <problem 1>
- <problem 2>
**Next steps:**
1. <action 1>
2. <action 2>
**Related tasks:** <task IDs from 03-tasks/>
**Related bugs:** <bug IDs from 04-bugs/>
```

---

## Session Log

<!-- Add new sessions below this line. Most recent first. -->

---

## [2026-04-04] — Session #002

**Goal:** Fix B003 (IBWorker re-entrant queue submission), B004 (dry_run inconsistency), B002 (break up minute_snapshot.py), and other open bugs; update all documentation

**Started:** 03:30 | **Ended:** — | **Outcome:** IN PROGRESS

**Context restored from:** Session S001 (docs restructuring), bug tracker B001-B010, task tracker T003/T004

**Decisions made:**
- B003: Adopt Option B from T004 design — use `threading.Timer` for reconnect so it never blocks the IB queue. Add `_schedule_reconnect()` method that wraps `connect()` in a short-lived background thread, bypassing `_submit_to_ib_thread` entirely.
- B004: `order_manager.place_and_finalize` gains a `dry_run` parameter. When `dry_run=True`, it returns a simulated success result without calling `ib_client.place_order`. `orders.execute_order` passes through `dry_run` to `place_and_finalize`.
- B002: Break `run_minute_snapshot` into sub-functions per T003 design: `_build_context`, `_fetch_and_cache`, `_handle_stale_bars`, `_compute_snapshot_rows`, `_write_snapshot_log`. Use `SnapshotContext` dataclass to carry intermediate state.
- B009: Replace `docs/` line in `.gitignore` with `docs/PRD_sell_manager_CLI.md` and `docs/PRD_sell_manager_CLI.md` (already listed separately at line 4); add `docs/*.tmp` for generated docs.
- B008: Add `**/__pycache__/` and `**/*.pyc` patterns to `.gitignore`.
- B010: Fix `clean_export.py` ignore patterns: add `'**/__pycache__'`, `'**/*.pyc'`, `'**/*.egg-info'`.
- B006: Create `utils/ticker.py` with `normalise_ticker()` used by both `ib_worker.py` and `widgets.py`.
- B005/B007: Add `use_rth` column to `assigned_ma.csv`, wire through `assign.py`, expose in `SettingsWidget` and persist via `settings_store.py`.

**New information learned:**
- `orders.py` already has a `dry_run` parameter but the live path calls `order_manager.place_and_finalize` without passing it through — fix needed.
- `ib_worker.py`'s reconnect path uses `threading.Timer` but submits back to `_submit_to_ib_thread` — creating the re-entrant queue problem.
- The `minute_snapshot.py` function is actually 571 lines, not 400.
- `.gitignore` already has `docs/PRD_sell_manager_CLI.md` at line 4, so `docs/` itself can be tracked (minus generated files).

**Problems encountered:**
- B001 (`__main__.py` monolith) requires significant refactoring across many files — deferred to a dedicated session.

**Next steps:**
1. Fix B003 (IBWorker re-entrant queue) — IN PROGRESS
2. Fix B004 (dry_run inconsistency) — after B003
3. Fix B002 (break up minute_snapshot.py) — after B004
4. Fix B009/B008/B010 (gitignore/clean_export) — quick wins
5. Fix B006 (symbol normalisation) — moderate effort
6. Fix B005/B007 (use_rth) — moderate effort
7. Defer B001 to dedicated session

**Related tasks:** T002, T003, T004, T005
**Related bugs:** B001, B002, B003, B004, B005, B006, B007, B008, B009, B010

---

## [2026-04-04] — Session #001

**Goal:** Full codebase review, restructure docs folder with numbering, create architecture doc, session tracker, task tracker, and bugs tracker

**Started:** 02:45 | **Ended:** — | **Outcome:** IN PROGRESS

**Context restored from:** N/A (first session under new docs structure)

**Decisions made:**
- Adopted 6-folder numbered docs structure: `00-project/`, `01-architecture/`, `02-sessions/`, `03-tasks/`, `04-bugs/`, `05-reference/`, `06-user-guide/`
- Created `tmp/` at project root for temporary working scripts
- Task tracker uses two-level design: `00-task-tracker.md` (summary + links) + `03-tasks/tracker/*.md` (expanded context)
- Bugs tracker uses single flat file for simplicity, with links to expanded tracker files
- Session tracker is a living append-only document (newest-first)

**New information learned:**
- Project uses `src/` layout with editable install (`pip install -e .`)
- GUI uses PySide6/qtpy with a dedicated IB thread via `queue.Queue`
- The `_poll_positions` method in `ib_worker.py` has a reconnect loop that submits tasks back to the same `_submit_to_ib_thread` queue — this creates a potential re-entrant call queue submission pattern
- The `minute_snapshot.py` has extensive logic for 30m → 1h aggregation, freshness detection, stale backfill, and per-ticker snapshot computation all in one large function
- The CLI `__main__.py` contains the full minute loop including interactive assignment prompts during runtime — this mixes UI concerns into the core module

**Problems encountered:**
- No issues encountered during review — this was a planning/documentation session

**Progress:**
- [x] Explore codebase structure
- [x] Read all existing docs
- [x] Design and create new docs folder structure
- [x] Create `docs/00-project/00-readme.md`
- [x] Create `docs/00-project/01-charter.md`
- [x] Create `docs/01-architecture/00-architecture-overview.md`
- [x] Create `docs/02-sessions/00-session-tracker.md` with S001 entry
- [x] Create `docs/03-tasks/00-task-tracker.md` (summary index)
- [x] Create `docs/03-tasks/tracker/T001-*.md` (expanded context)
- [x] Create `docs/04-bugs/00-bug-tracker.md` with 10 bug entries (B001-B010)
- [x] Create `docs/05-reference/` (index, config-files, module-api, runbook)
- [x] Create `docs/06-user-guide/00-user-guide.md`
- [x] Create `tmp/README.md` for temporary scripts folder
- [x] Update `scripts/__init__.py` with documentation
- [ ] Verify all files render correctly

**Next steps:**
1. Verify all documentation files render correctly in the IDE
2. Consider adding `!docs/` to `.gitignore` to track documentation (B009)
3. Start work on T002 (extract interactive prompts from `__main__.py`)
4. Start work on T003 (break up `minute_snapshot.py`)
5. Address B008 and B009 (gitignore improvements)

**Related tasks:** T002, T003, T004, T005
**Related bugs:** B001, B002, B003, B004, B005, B006, B007, B008, B009, B010

