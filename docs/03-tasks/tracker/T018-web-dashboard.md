# T018 — Local web dashboard (snapshot + signals)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T018 |
| Title | Flask read-only dashboard for latest minute snapshot and recent signals |
| Status | DONE |
| Session completed | S010 |
| Priority | P3 |
| Created | 2026-04-04 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed: web dashboard |
| Detail File | `docs/03-tasks/tracker/T018-web-dashboard.md` |

---

## 1. Goal

Serve a small HTML page on **127.0.0.1** showing the latest `logs/minute_snapshot.jsonl` record and the most recent batch from `logs/signals.jsonl`.

## 2. Resolution

- `dashboard.py`: `create_app`, `run_dashboard`, `read_latest_snapshot_record`, `dashboard_port`.
- `flask>=3.0` in `[gui]` extra; CLI `sellmanagement dashboard --host 127.0.0.1`.
- Port: `SELLMANAGEMENT_DASHBOARD_PORT` (default **5055**).
- Tests: `tests/test_dashboard.py`.

## 3. Acceptance

- [x] Delivered
