# T011 — `cli_executor` tests

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T011 |
| Title | Unit tests for `transmit_live_sell_signals` |
| Status | DONE |
| Priority | P3 |
| Session completed | S007 |
| Detail File | `docs/03-tasks/tracker/T011-cli-executor-tests.md` |

---

## 1. Resolution (S007)

`tests/test_cli_executor.py`: skips non–SellSignal; live SellSignal path calls `execute_order` with `dry_run=False` (mocked).
