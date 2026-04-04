# T021 — Broker adapter package (`brokers/` + IBKR)

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T021 |
| Title | `sellmanagement.brokers` package; IBKR implementation in `ibkr.py` |
| Status | DONE |
| Session completed | S013 |
| Parent | Spawned from [T015](T015-product-backlog.md) seed: broker adapters beyond IBKR |
| Detail File | `docs/03-tasks/tracker/T021-broker-adapters.md` |

---

## 1. Goal

Introduce a **`brokers/`** namespace for execution/data backends. Move the existing Interactive Brokers (`ib_insync`) implementation into **`brokers/ibkr.py`** as **`IBKRBroker`**, while keeping **`ib_client.IBClient`** as a stable alias for callers.

## 2. Resolution

- `brokers/ibkr.py` — full IBKR session + order surface (formerly `ib_client.py` body).
- `brokers/__init__.py` — exports `IBKRBroker`, `create_broker("ibkr", **kwargs)`.
- `ib_client.py` — `from .brokers.ibkr import IBKRBroker as IBClient`.
- Tests: `tests/test_brokers.py`.
- Architecture + module API + runbook updated.

## 3. Acceptance

- [x] Delivered
