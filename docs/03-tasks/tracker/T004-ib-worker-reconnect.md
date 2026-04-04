# T004 — Fix Reconnect Loop in `IBWorker`

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T004 |
| Title | Fix reconnect loop in `IBWorker._poll_positions` |
| Status | DONE |
| Priority | P1 |
| Created | 2026-04-04 |
| Session completed | S002 |
| Last verified | S003 |
| Detail File | `docs/03-tasks/tracker/T004-ib-worker-reconnect.md` |

---

## 1. Goal

Separate the "work" queue (position polling) from the "control" operations (connect/disconnect/reconnect) in `IBWorker`, preventing re-entrant queue submissions and ensuring reconnect logic is handled cleanly.

---

## 2. Background

**Bug (B003):** When `_poll_positions` encounters 3 or more consecutive errors, it calls `self.connect(...)`. Since `_poll_positions` is itself submitted via `_submit_to_ib_thread`, and `connect` also submits work to the same queue via `_submit_to_ib_thread`, this creates a re-entrant queue submission pattern.

Additionally, `connect` is a potentially blocking call (it waits for IB connection with a timeout), and running it on the queue worker thread means other queued work is blocked during the connection attempt.

---

## 3. Design Options

### Option A: Separate Control Queue

Introduce a second `queue.Queue` exclusively for control operations:

```
work_queue    → _poll_positions, _fetch
control_queue → connect, disconnect, reconnect
```

Control operations run on a separate thread, so they never block the work queue.

### Option B: Dedicated Reconnect Timer

Handle reconnect outside both queues using a `threading.Timer` or `QTimer`:

```python
def _poll_positions(self):
    try:
        raw = self._client.positions()
        ...
    except Exception:
        self._consecutive_errors += 1
        if self._consecutive_errors >= 3:
            self._schedule_reconnect()  # fires after backoff, runs connect() directly
```

The reconnect call runs on the main (GUI) thread or a dedicated short-lived thread, bypassing the IB queue entirely.

### Option C: Use `run_on_thread` for Reconnect

The `run_on_thread` method already exists. Use it for the reconnect:

```python
def _poll_positions(self):
    ...
    if errors >= 3:
        self.run_on_thread(lambda: self.connect(*saved_params))
```

This is already partially implemented but submits back to the same queue via `_submit_to_ib_thread`.

---

## 4. Recommended Approach

**Option B** is recommended: use a `threading.Timer` for reconnect so it never blocks the IB worker queue.

---

## 5. Acceptance Criteria

- [x] Reconnect logic does not submit work back into the IB queue — `_schedule_reconnect` runs `connect()` on a short-lived daemon thread (S002); verified in S003.
- [x] `consecutive_errors` counter is reset on successful poll — `_consecutive_poll_errors` reset to `0` after a successful `_fetch` in `_poll_positions` (S002).
- [x] Backoff timer is cancelled on clean disconnect — `disconnect()` cancels `_reconnect_timer` (S002).
- [x] Unit tests: 3-error reconnect trigger + error counter reset — `tests/test_ib_worker.py` (S007). Disconnect-during-reconnect remains optional coverage.

## 6. Implementation notes (S002 / S003)

- Chosen design matches **Option B** intent: reconnect work is not queued on `_call_queue`; `_schedule_reconnect` spawns a daemon `threading.Thread` that calls `connect()`.
- `connect` failure path uses `threading.Timer` only to delay the call; the timer callback invokes `_schedule_reconnect`, not `_submit_to_ib_thread`.
