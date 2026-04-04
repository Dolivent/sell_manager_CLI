# T020 — Strategy presets (MA assignments) JSON import/export

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T020 |
| Title | Import/export `assigned_ma.csv` as JSON (CLI + GUI) |
| Status | DONE |
| Session completed | S012 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed: strategy presets |
| Detail File | `docs/03-tasks/tracker/T020-ma-presets-json.md` |

---

## 1. Goal

Operators can snapshot and restore MA assignment tables without hand-editing CSV.

## 2. Resolution

- `assign.export_assignments_json(path)` / `assign.import_assignments_json(path, merge=False)`.
- CLI: `sellmanagement ma-export <path>` / `sellmanagement ma-import <path> [--merge]`.
- GUI: Settings tab — **Export MA preset…**, **Import MA preset…**, optional **merge** checkbox; `assignments_changed` signal refreshes Positions tab.
- Preset shape: `{"version": 1, "assignments": [{ticker, type, length, timeframe}, ...]}` (or a bare JSON array).
- Tests: `tests/test_ma_presets.py`.

## 3. Acceptance

- [x] Delivered
