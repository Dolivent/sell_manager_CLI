# Project Charter

> **Version:** 1.0 | **Status:** Active | **Last Updated:** 2026-04-04

---

## 1. Project Overview

**Name:** sell_manager_CLI  
**Type:** Automated trading decision-support CLI + GUI  
**Core Functionality:** Monitors Interactive Brokers (IB) positions; prepares and optionally transmits full-close sell orders when a position's latest close crosses below an assigned moving average.  
**Target Users:** Active traders using IBKR (IB Gateway or TWS) who follow a mechanical moving-average exit strategy.

---

## 2. Goals

- Zero surprise live orders — explicit user confirmation required before any transmission
- Full audit trail: every signal, order attempt, and lifecycle event is logged
- Robust to IB Gateway disconnects and resume-from-sleep scenarios
- Clean separation between data ingestion, signal generation, and order execution layers
- Both CLI (terminal) and GUI (Qt) modes from a single codebase

---

## 3. Non-Goals

- Partial position sells (always full-close)
- Portfolio-level or multi-leg order management
- Real-time tick-level data (minute-bar granularity only)
- Backtesting or historical strategy evaluation

---

## 4. Key Decisions (Log)

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-04 | Adopt numbered docs folder structure | High context drift; stable cross-session references required |
| 2026-04-04 | Separate tracker files from summary index | Prevents unreadable trackers while preserving full context |
| 2026-04-04 | Use `src/` layout + editable install | Required for clean module imports and packaging |
| 2026-04-04 | America/New_York timezone for all timestamps | Trading hours are NY-based; IB stores bars in local/exchange TZ |
| 2026-04-04 | Append-only audit logs (JSONL) | Crash-safe, pipeline-friendly, easy to tail |
| 2026-04-04 | Idempotency via SHA256 intent keys | Prevents duplicate order attempts on restart/reconnect |

---

## 5. Glossary

| Term | Definition |
|------|-----------|
| MA | Moving Average (SMA or EMA) |
| SMA | Simple Moving Average |
| EMA | Exponential Moving Average |
| IB / IBKR | Interactive Brokers |
| dry-run | Simulation mode — orders prepared but not transmitted |
| live mode | Orders transmitted to IB |
| abv_be | Above Break-Even — safety gate: `close > avgCost AND ma > avgCost` |
| SellSignal | Decision output when close < MA and abv_be is True |
| NoSignal | No action warranted |
| intent_id | SHA256 hash of `{ticker}:{bucket_ts}:{decision}` used for idempotency |
| 1H | Hourly evaluation timeframe |
| 1D | Daily evaluation timeframe |
