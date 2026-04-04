# GUI smoke checklist

> **Purpose:** Quick regression pass after CLI or core changes.  
> **Last updated:** 2026-04-04 (S007)

---

## Prerequisites

- `pip install -e ".[gui]"`
- IB Gateway or TWS logged in (paper recommended)
- Port matches Settings (default `4001`)

---

## Checklist

1. **Launch:** `python -m sellmanagement --gui` — window opens without traceback.
2. **Settings:** Host, port, client ID visible; toggle **Use RTH** and **Live** if present — no crash.
3. **Connect:** Enable connection — status indicates connected; console / log shows no repeated errors.
4. **Positions:** After connect, positions table updates (or shows empty with clear state).
5. **Assigned MA:** Table loads from `assigned_ma.csv`; edit a cell if needed — saves without error.
6. **Pipeline / snapshot:** If you use the pipeline control, run a one-shot snapshot or start pipeline — completes or surfaces a clear error (e.g. missing assignment).
7. **Disconnect:** Disconnect or close window — clean exit, no hang.

---

## Headless / CI

Automated tests use `QT_QPA_PLATFORM=offscreen` and **do not** require a visible display. This checklist is for **human** verification on a workstation.
