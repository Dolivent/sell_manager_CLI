# T010 — Trace / `append_trace` tests

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T010 |
| Title | Tests for trace logging output |
| Status | DONE |
| Priority | P3 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T010-trace-tests.md` |

---

## 1. Resolution (S007)

`tests/test_trace.py`: patches `_trace_path` to a temp file; closes `RotatingFileHandler` after use so **Windows** can delete the temp directory.

---

## 2. Acceptance

- [x] JSON line shape verified (`event`, `ts`)
