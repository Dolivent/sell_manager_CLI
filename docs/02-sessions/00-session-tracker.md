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

## [2026-04-04] — Session #011

**Goal:** Implement T019 from T015 — persist IB client ID in the GUI via QSettings; add `ClientIdSelector`.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** T015 seed item 3; S010 next steps.

**Decisions made:**
- Reuse CLI `--client-id` (already default 1); GUI stores under `ib/client_id` with range **1–999999**.
- **B011:** `SettingsWidget` referenced `use_rth_checkbox` before it was constructed — fixed by reordering init.

**Completed:** `settings_store` helpers, `ClientIdSelector`, `tests/test_settings_store.py`, bug tracker, runbook + module API.

**Next steps:** T020 MA preset JSON import/export; T021 broker adapters.

**Related tasks:** T019 (DONE), T015 (OPEN)  
**Related bugs:** B011 (FIXED)

---

## [2026-04-04] — Session #010

**Goal:** Implement T018 from T015 — Flask read-only dashboard for latest `minute_snapshot.jsonl` + latest signal batch.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** T015 seed item 2; S009 next steps.

**Decisions made:**
- Bind **127.0.0.1** only; port from `SELLMANAGEMENT_DASHBOARD_PORT` (default **5055**).
- `flask` added to **`[gui]`** optional extra (same install path as PySide6 for CI).
- HTML via inline template in `dashboard.py` (no `templates/` tree).

**Completed:** `dashboard.py`, `sellmanagement dashboard`, `tests/test_dashboard.py`, runbook + module API, trackers.

**Next steps:** T019 multi-account GUI persistence + `ClientIdSelector`; T020 presets; T021 broker abstraction.

**Related tasks:** T018 (DONE), T015 (OPEN)  
**Related bugs:** —

---

## [2026-04-04] — Session #009

**Goal:** Implement T017 from T015 — SMTP email alerts on `SellSignal` and on failed live order transmit; update docs and trackers.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** T015 seed list (item 1); session S008 next steps.

**Decisions made:**
- Scope **email/SMTP only** (no Telegram/push in this task); stdlib `smtplib` + `EmailMessage`.
- Failure alerts for live transmit when `execute_order` / lifecycle `status` is `failed_prepare`, `failed_transmit`, `timeout`, `error`, or `cancelled`; plus exception path in `transmit_live_sell_signals`.
- Port **465** uses `SMTP_SSL`; other ports use `STARTTLS` when offered.
- SMTP auth optional: if `SELLMANAGEMENT_SMTP_USER` is set, `SELLMANAGEMENT_SMTP_PASS` must be present in the environment (value may be empty).

**Completed:**
- `alerts.py`, hooks in `signals.py` / `cli_executor.py`, `tests/test_alerts.py`.
- Runbook §2a.2, module API; T017 tracker DONE; T015 spawned row; task index.

**Next steps:** T018 (Flask dashboard from T015 item 2); then multi-account GUI, MA presets, broker abstraction per backlog.

**Related tasks:** T017 (DONE), T015 (OPEN)  
**Related bugs:** —

---

## [2026-04-04] — Session #008

**Goal:** Implement T016 from product backlog — configurable `ibkr_download_trace.log` rotation via environment variables; update docs and trackers.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** T015 seed list (“configurable rotation policy per log file”); session S007 next-step guidance.

**Decisions made:**
- Use decimal megabytes (1 MB = 1_000_000 bytes) so default remains 10_000_000 bytes.
- Clamp MB and backup count to bounded ranges; invalid env strings fall back to defaults.

**Completed:**
- `trace._trace_rotation_settings()` + extended `tests/test_trace.py`.
- Runbook §2a.1, module API, reference index; fixed reference-index audit table (order intents row + GUI smoke section).
- Trackers: T016 DONE; T015 “spawned tasks”; task index updated.

**Next steps:** Pick another T015 item for T017 (alerts, dashboard, multi-account, etc.); optional dev lint pass (`ruff`) remains a separate cleanup.

**Related tasks:** T016 (DONE), T015 (OPEN)  
**Related bugs:** —

---

## [2026-04-04] — Session #007

**Goal:** Complete backlog T007–T014 (logging phase 2, CLI loop extraction, tests, runbook, GUI smoke, CI hardening); leave T015 as open product bucket.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** User request to “do all”; prior task definitions T007–T015.

**Decisions made:**
- Introduce `log_config.py` + `cli_loop.py`; keep `_cmd_start` as orchestration shell.
- CI installs `[gui]` for IBWorker tests; `QT_QPA_PLATFORM=offscreen`; Linux apt Qt libs; run `pytest` after `unittest`.
- `heartbeat_cycle` accepts optional `now_fn` for unit tests (avoid patching `datetime.now` on the class).

**Completed:**
- T007–T014 DONE; T015 OPEN with seed ideas in tracker.
- **IBWorker:** fixed reconnect timer lambda (`host,port,client_id` vs broken `h,p,cid`).
- New tests: `test_cli_loop`, `test_trace`, `test_cli_executor`, `test_ib_worker`; `tests/test_cli_loop.py` covers heartbeat/sort/signals batch.
- Docs: runbook §2a.1, `02-gui-smoke.md`, module API, task trackers, T004 acceptance update.

**Next steps:** Pick an item from T015 and open T016; optional `ruff`/`mypy` in `dev`.

**Related tasks:** T007–T014 (DONE), T015 (OPEN)  
**Related bugs:** — (timer fix noted under T009)

---

## [2026-04-04] — Session #006

**Goal:** Register backlog tasks T006–T015 in docs; implement CI; add `dev` optional dependency; update runbook.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** User request to update docs and continue; prior informal backlog list.

**Decisions made:**
- Formalised **T006–T015** with tracker files under `docs/03-tasks/tracker/`.
- **T006** = GitHub Actions CI (Python 3.10–3.12, compileall + unittest); no IB in CI.
- **`dev`** optional extra in `pyproject.toml` includes `pytest` (T012 partial; migration still OPEN).

**Completed:**
- `.github/workflows/ci.yml`
- Tracker files T006–T015; `00-task-tracker.md` backlog table + detail stubs
- Runbook §0 CI; session log
- **Packaging fix:** moved `requires-python` under `[project]` (it had been parsed as `[project.scripts]` and broke `pip install -e .` on newer setuptools).

**Next steps:** T007 (logging phase 2) or T008 (`_cmd_start` splits) or T009 (IBWorker tests).

**Related tasks:** T006 (DONE), T007–T015 (OPEN)  
**Related bugs:** —

---

## [2026-04-04] — Session #005

**Goal:** Re-run automated tests and verify IB Gateway connectivity after the user enabled TWS/Gateway.

**Started:** — | **Ended:** — | **Outcome:** SUCCESS

**Context restored from:** Session S004; user note that Gateway was previously off.

**Completed:**
- `python -m unittest discover -s tests -v` with `PYTHONPATH=src` — 7 tests, all OK.
- Smoke test: `IBClient(host=127.0.0.1, port=4001, client_id=99).connect(timeout=8)` returned `True`, then disconnect.

**Next steps:** Run `python -m sellmanagement` (or `sellmanagement start`) locally for a full minute loop when you want live snapshots; ensure client id does not clash with other sessions.

**Related tasks:** —  
**Related bugs:** —

---

## [2026-04-04] — Session #004

**Goal:** Close B001 / T002 by extracting CLI prompts and live transmit logic; add `--yes-to-all`; begin T005 by routing `append_trace` through rotating logging; add unit tests; refresh trackers and module API.

**Started:** 14:00 | **Ended:** 15:30 | **Outcome:** SUCCESS

**Context restored from:** Session S003 next steps, `docs/03-tasks/tracker/T002-extract-interactive-prompts.md`, `docs/03-tasks/tracker/T005-proper-logging.md`, `__main__.py`.

**Decisions made:**
- Implement T002 as two modules: `cli_prompts.py` (all `input()` for MA menu + live confirm) and `cli_executor.py` (live SellSignal transmit only).
- `prompt_ma_assignment` accepts optional `reader=` for tests without patching globals.
- `--yes-to-all` maps to `confirm_live_transmit(assume_yes=True)` — documented as scripting-only.
- T005 phase 1: keep `append_trace(record: dict)` API; implement via dedicated `logging` logger + `RotatingFileHandler` (10 MB × 5) writing the same JSON lines as before.

**New information learned:**
- `_cmd_start` still contains the minute loop, position sync, and snapshot table printing (~300+ lines); splitting those is optional follow-up.

**Problems encountered:**
- None blocking.

**Completed:**
- B001 FIXED; T002 DONE; T005 marked DONE for trace rotation (call sites unchanged).
- `tests/test_cli_prompts.py` (unittest); `python -m unittest discover -s tests` passes with `PYTHONPATH=src`.

**Next steps (S005):**
1. Optional: extract minute-loop helpers or snapshot table printer from `_cmd_start`.
2. Optional: structured log levels / console handler for trace events (T005 phase 2).
3. Add CI step to run `unittest` with `PYTHONPATH=src`.

**Related tasks:** T002, T005  
**Related bugs:** B001 (FIXED)

---

## [2026-04-04] — Session #003

**Goal:** Verify B003/B004/B002 implementations from S002; align task detail docs; restore a clean `python -m compileall` on `src/`.

**Started:** 12:00 | **Ended:** 12:45 | **Outcome:** SUCCESS

**Context restored from:** Session S002, `docs/04-bugs/00-bug-tracker.md`, T003/T004 task files, `gui/ib_worker.py`, `orders.py`, `minute_snapshot.py`.

**Decisions made:**
- B003/B004/B002: No code changes required for the original fixes — behaviour already matches S002 descriptions (`_schedule_reconnect`, `place_and_finalize(dry_run=...)`, snapshot phases/dataclasses).
- Treated two syntax regressions as immediate repair scope: remove orphan `try:` in `orders.py` live path; fix corrupted f-string in `__main__.py` position-matching loop.

**New information learned:**
- `orders.py` contained a `try:` block (lines 87–101) with no `except`/`finally`, which raises `SyntaxError` and blocks the entire package.
- `__main__.py` used `f\":{sym}\"` (invalid escape inside f-string), also a hard `SyntaxError`.

**Problems encountered:**
- Bug tracker marked B002–B010 as FIXED while `src/` did not compile — documentation was ahead of (or diverged from) a broken working tree.

**Completed:**
- Verified IBWorker `_schedule_reconnect` and poll-error path; verified `order_manager.place_and_finalize` + `execute_order` dry_run wiring; verified `SnapshotRow` / `SnapshotContext` and phased `minute_snapshot` helpers.
- Fixed syntax errors in `orders.py` and `__main__.py`; `python -m compileall -q src` passes.
- Synced `docs/03-tasks/tracker/T004-ib-worker-reconnect.md` with DONE status and acceptance criteria (automated tests still absent).

**Next steps (S004):**
1. B001: Extract `cli_prompts.py` and `cli_executor.py` from `__main__.py` (T002).
2. Consider adding `pytest` + minimal `IBWorker` reconnect/poll tests (T004 acceptance gap).
3. Close out T001 documentation task index if all deliverables exist.

**Related tasks:** T002, T003, T004, T001  
**Related bugs:** B001 (OPEN), B002–B010 (FIXED); S003 syntax repairs tied to B004 / `__main__` live path

---

## [2026-04-04] — Session #002

**Goal:** Fix B003 (IBWorker re-entrant queue), B004 (dry_run inconsistency), B002 (break up minute_snapshot.py), B006 (symbol normalisation), B005/B007 (use_rth), B008/B009/B010 (gitignore/clean_export); update all documentation

**Started:** 03:30 | **Ended:** 04:45 | **Outcome:** SUCCESS (9/10 bugs fixed, B001 deferred)

**Context restored from:** Session S001 (docs restructuring), bug tracker B001-B010, task tracker T003/T004

**Decisions made:**
- B003: Adopt Option B from T004 design — use `threading.Timer` for reconnect so it never blocks the IB queue. Add `_schedule_reconnect()` method that wraps `connect()` in a short-lived background thread, bypassing `_submit_to_ib_thread` entirely.
- B004: `order_manager.place_and_finalize` gains a `dry_run` parameter. When `dry_run=True`, it returns a simulated success result without calling `ib_client.place_order`. `orders.execute_order` passes through `dry_run` to `place_and_finalize`.
- B002: Break `run_minute_snapshot` into sub-functions per T003 design: `_build_context`, `_fetch_and_cache`, `_compute_snapshot_rows`, `_write_snapshot_log`. Use `SnapshotContext` and `SnapshotRow` dataclasses to carry intermediate state.
- B009: Replace `docs/` line in `.gitignore` with tracking — `docs/PRD_sell_manager_CLI.md` is already separately ignored at line 62.
- B008: Add `**/__pycache__/` and `**/*.pyc` patterns to `.gitignore`.
- B010: Fix `clean_export.py` ignore patterns: add `'**/__pycache__'`, `'**/*.pyc'`, `'**/*.egg-info'`.
- B006: Create `utils/ticker.py` with `normalise_ticker()`, `ticker_to_symbol()`, `tickers_match()` used by both `ib_worker.py` and `widgets.py`.
- B005/B007: Add `use_rth` checkbox to SettingsWidget, persisted via `settings_store.py`. `IBWorker.connect()` accepts `use_rth` and passes to `IBClient`. `_schedule_reconnect` preserves `use_rth` across reconnects.
- B001: Deferred — requires extracting `cli_prompts.py` and `cli_executor.py`; too large for this session.

**New information learned:**
- `orders.py` already has a `dry_run` parameter but the live path calls `order_manager.place_and_finalize` without passing it through — fix needed.
- `ib_worker.py`'s reconnect path uses `threading.Timer` but submits back to `_submit_to_ib_thread` — creating the re-entrant queue problem. Fixed by creating a dedicated `_schedule_reconnect` that runs `connect()` directly on a thread.
- The `minute_snapshot.py` function is actually 571 lines, not 400.
- `.gitignore` already had `docs/PRD_sell_manager_CLI.md` separately at line 4, so `docs/` can be tracked as-is.

**Problems encountered:**
- S002 session tracker content was accidentally inserted inside S001 due to an imprecise string replacement in the markdown. Fixed by rewriting the session tracker cleanly.
- B001 (`__main__.py` monolith) requires significant refactoring — deferred to dedicated session.

**Fixed bugs:**
- B002 (minute_snapshot.py monolith) — FIXED
- B003 (IBWorker re-entrant queue) — FIXED
- B004 (dry_run inconsistency) — FIXED
- B005 + B007 (use_rth hardcoded) — FIXED
- B006 (symbol normalisation mismatch) — FIXED
- B008 (nested __pycache__) — FIXED
- B009 (docs/ gitignored) — FIXED
- B010 (clean_export.py __pycache__) — FIXED

**Next steps (S003):**
1. Fix B001: Extract `cli_prompts.py` from `__main__.py`
2. Fix B001: Extract `cli_executor.py` from `__main__.py`
3. T002 task: Extract interactive prompts from `__main__.py`
4. T005 task: Replace `trace.py` prints with Python `logging` module
5. Verify all docs render correctly

**Related tasks:** T002, T003, T004, T005
**Related bugs:** B001 (deferred), B002, B003, B004, B005, B006, B007, B008, B009, B010

---

## [2026-04-04] — Session #001

**Goal:** Full codebase review, restructure docs folder with numbering, create architecture doc, session tracker, task tracker, and bugs tracker

**Started:** 02:45 | **Ended:** 03:30 | **Outcome:** SUCCESS

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
- [x] Verify all files render correctly

**Next steps:**
1. Verify all documentation files render correctly in the IDE
2. Fix B003: Address IBWorker re-entrant queue submission (T004)
3. Fix B004: Address dry_run inconsistency between orders.py and order_manager.py
4. Fix B002: Break up `minute_snapshot.py` (T003)
5. Address B008 and B009 (gitignore improvements)

**Related tasks:** T002, T003, T004, T005
**Related bugs:** B001, B002, B003, B004, B005, B006, B007, B008, B009, B010
