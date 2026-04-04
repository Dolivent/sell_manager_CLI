# T017 — SMTP email alerts (SellSignal + failed live orders)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T017 |
| Title | Email alerts via SMTP for SellSignal and failed order transmit |
| Status | DONE |
| Session completed | S009 |
| Priority | P3 |
| Created | 2026-04-04 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed: push/email/Telegram (email/SMTP scope) |
| Detail File | `docs/03-tasks/tracker/T017-smtp-alerts.md` |

---

## 1. Goal

When a **SellSignal** is logged to `logs/signals.jsonl`, optionally send an email. When a **live** order transmit returns a failure status (or raises in the transmit path), optionally send an email.

Configuration via environment variables only; if incomplete, log a warning once per process and skip.

## 2. Resolution

- `alerts.py`: `send_smtp_alert`, `alert_sellsignal_logged`, `order_transmit_needs_alert`, `alert_order_failed`, `alert_order_exception`.
- Env: `SELLMANAGEMENT_SMTP_HOST`, `SELLMANAGEMENT_SMTP_PORT` (default 587), `SELLMANAGEMENT_SMTP_USER` / `SELLMANAGEMENT_SMTP_PASS` (optional pair; port **465** uses SSL).
- Hooks: `signals.append_signal` after successful write for `SellSignal`; `cli_executor.transmit_live_sell_signals` on failure statuses (`failed_prepare`, `failed_transmit`, `timeout`, `error`, `cancelled`) and on transmit exceptions.
- Incomplete env: one **WARNING** per process, then skip.
- Tests: `tests/test_alerts.py`.

## 3. Acceptance

- [x] Implemented and documented
