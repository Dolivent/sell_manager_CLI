# T007 — Logging phase 2 (console + module loggers)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T007 |
| Title | T005 phase 2 — console and leveled logging |
| Status | DONE |
| Priority | P2 |
| Created | 2026-04-04 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T007-logging-phase2.md` |

---

## 1. Resolution (S007)

- `log_config.setup_logging()` attaches a **stderr** `StreamHandler` at **WARNING** to the `sellmanagement` logger (idempotent).
- Called from `__main__.main()` and `gui/run_gui.main()`.
- `downloader.py`: `logger.warning` on halfhour backfill request failure (alongside `append_trace`).
- `trace.append_trace`: on failure, logs `WARNING` with `exc_info` to `sellmanagement` logger.

Further optional work: migrate more modules from `print` / `append_trace` to named loggers with DEBUG/INFO levels.

---

## 2. Acceptance

- [x] Documented log policy (runbook + module API)
- [x] Console handler for CLI/GUI startup path
- [x] At least one non-trace module uses `logging.getLogger(__name__)` (`downloader`)
