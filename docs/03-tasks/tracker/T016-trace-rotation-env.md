# T016 — Configurable trace log rotation (environment)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T016 |
| Title | Trace `RotatingFileHandler` policy via environment variables |
| Status | DONE |
| Priority | P3 |
| Created | 2026-04-04 |
| Session completed | S008 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed idea: configurable rotation per log file |
| Detail File | `docs/03-tasks/tracker/T016-trace-rotation-env.md` |

---

## 1. Goal

Allow operators to tune `logs/ibkr_download_trace.log` rotation without code changes.

## 2. Resolution

- `sellmanagement.trace._trace_rotation_settings()` reads:
  - `SELLMANAGEMENT_TRACE_MAX_MB` — float; each unit is **1,000,000 bytes** (matches the previous fixed 10_000_000 default).
  - `SELLMANAGEMENT_TRACE_BACKUPS` — integer; `0` means no extra rotated files kept.
- Invalid values fall back to defaults (10 MB, 5 backups). Clamps: MB in `[0.1, 1024]`, backups in `[0, 100]`.
- Documented in runbook §2a.1, module API, reference index.
- Tests: `tests/test_trace.py` (env parsing, handler `maxBytes` / `backupCount`).

## 3. Acceptance

- [x] Defaults unchanged when env vars unset
- [x] Unit tests cover env override and invalid fallback
- [x] Docs updated
