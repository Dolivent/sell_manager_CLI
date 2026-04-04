# T006 — CI pipeline (compile + unit tests)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T006 |
| Title | CI pipeline |
| Status | DONE |
| Priority | P2 |
| Created | 2026-04-04 |
| Session completed | S006 (initial), S007 (GUI + pytest + Linux Qt deps) |
| Detail File | `docs/03-tasks/tracker/T006-ci-pipeline.md` |

---

## 1. Goal

Run `compileall` and `unittest` on every push/PR so regressions are caught without a local Gateway.

## 2. Implementation

- Workflow: `.github/workflows/ci.yml`
- Triggers: `push` / `pull_request` to `main` or `master`
- Matrix: Python 3.10, 3.11, 3.12
- `pip install -e ".[gui]"` (IBWorker tests), `QT_QPA_PLATFORM=offscreen`, Linux apt deps for Qt
- `compileall` → `unittest discover -s tests -v` → `pip install -e ".[dev]"` → `pytest tests -q`

## 3. Acceptance

- [x] Workflow file committed
- [x] Documented in runbook
