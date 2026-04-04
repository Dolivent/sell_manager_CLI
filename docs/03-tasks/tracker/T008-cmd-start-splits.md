# T008 — Further `_cmd_start` decomposition

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T008 |
| Title | Extract minute-loop helpers / snapshot table from `__main__.py` |
| Status | DONE |
| Priority | P2 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T008-cmd-start-splits.md` |

---

## 1. Resolution (S007)

New module `cli_loop.py`:

- `sleep_until_next_minute_ny`, `heartbeat_cycle` (optional `now_fn` for tests)
- `read_last_signal_batch`, `print_last_signals_preview`
- `sort_snapshot_rows_for_display`, `print_snapshot_table`

`__main__.py` delegates to these; orchestration and IB/sync loops remain in `_cmd_start`.

---

## 2. Acceptance

- [x] Clear single-purpose helpers
- [x] No intentional behaviour change in minute loop timing or table layout
