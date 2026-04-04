# T015 — Product backlog (placeholder)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T015 |
| Title | Feature backlog — alerts, reporting, multi-account |
| Status | OPEN |
| Priority | P3 |
| Created | 2026-04-04 |
| Detail File | `docs/03-tasks/tracker/T015-product-backlog.md` |

---

## 1. Goal

Capture non-bug product ideas. Split into new tasks when prioritized.

## 2. Seed ideas (unprioritised)

- Push/email/Telegram alert on `SellSignal` or on failed order
- Web dashboard for latest snapshot + signals
- Multi-account / sub-account selection
- Configurable rotation policy per log file
- Strategy presets (MA sets) import/export
- Broker adapters beyond IBKR

## 3. Spawned tasks

| ID | Item from seed list | Tracker |
|----|---------------------|---------|
| T016 | Configurable rotation policy per log file | [T016-trace-rotation-env.md](T016-trace-rotation-env.md) — **DONE** (S008) |
| T017 | Push/email/Telegram alert on SellSignal or failed order (SMTP email) | [T017-smtp-alerts.md](T017-smtp-alerts.md) — **DONE** (S009) |
| T018 | Web dashboard for latest snapshot + signals | [T018-web-dashboard.md](T018-web-dashboard.md) — **DONE** (S010) |
| T019 | Multi-account / client ID (GUI persistence + ClientIdSelector) | [T019-multi-account-client-id.md](T019-multi-account-client-id.md) — **DONE** (S011) |
| T020 | Strategy presets (MA sets) import/export | [T020-ma-presets-json.md](T020-ma-presets-json.md) — **DONE** (S012) |
| T021 | Broker adapters (`brokers/ibkr.py`, factory) | [T021-broker-adapters.md](T021-broker-adapters.md) — **DONE** (S013) |

## 4. Notes

This task stays **OPEN** as a bucket; spawn **T017+** for further product ideas when scoped.
