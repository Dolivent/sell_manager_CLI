# T009 — IBWorker automated tests

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T009 |
| Title | Unit tests for `IBWorker` reconnect / poll |
| Status | DONE |
| Priority | P2 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T009-ibworker-tests.md` |

---

## 1. Resolution (S007)

- `tests/test_ib_worker.py`: `QCoreApplication` fixture; mock client; synchronous `_submit_to_ib_thread`; three poll failures assert `_schedule_reconnect` called once; success resets `_consecutive_poll_errors`.
- **Bugfix:** `IBWorker.connect` reconnect `threading.Timer` callback used undefined `h,p,cid` — corrected to `host, port, client_id` from `connect()` parameters.

---

## 2. Acceptance

- [x] Tests run in CI without IB Gateway (`[gui]` install + offscreen Qt)
- [x] Reconnect scheduling path covered
