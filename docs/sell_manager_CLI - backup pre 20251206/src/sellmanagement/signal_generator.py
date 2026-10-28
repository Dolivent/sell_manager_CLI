"""Signal generator that reads minute snapshot log and appends signals.

This module provides helpers to read the latest `logs/minute_snapshot.jsonl`
entry and generate signal decision records (using `last_close` and
`ma_value`) which are appended via `signals.append_signal` for audit.

The module deliberately keeps scheduling out of scope; callers should
invoke `generate_signals_from_latest_snapshot` at the desired times
(top-of-hour, 15:59:55 ET, etc.).
"""
from pathlib import Path
import json
from typing import List, Dict, Any

from .signals import append_signal


def _snapshot_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "minute_snapshot.jsonl"


def read_latest_minute_snapshot() -> List[Dict[str, Any]]:
    """Return the rows array from the last minute_snapshot JSONL entry.

    Returns an empty list when the file is missing or no rows found.
    """
    p = _snapshot_path()
    if not p.exists():
        return []
    last = None
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                last = obj
            except Exception:
                continue
    if not last:
        return []
    return last.get("rows", []) or []


def _make_entry_from_row(row: Dict[str, Any], decision: str) -> Dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "decision": decision,
        "close": row.get("last_close"),
        "ma_value": row.get("ma_value"),
        "assigned_timeframe": row.get("assigned_timeframe"),
        "assigned_ma": row.get("assigned_ma"),
        "assigned_length": row.get("assigned_length"),
        "assigned_type": row.get("assigned_type"),
        # propagate sizing info so callers can act (e.g., prepare full-close orders)
        "position": row.get("position"),
        "avg_cost": row.get("avg_cost"),
    }


def generate_signals_from_rows(rows: List[Dict[str, Any]], evaluate_hourly: bool = True, evaluate_daily: bool = False, dry_run: bool = True) -> List[Dict[str, Any]]:
    """Generate and append signals for provided snapshot `rows`.

    - If `evaluate_hourly` is True, rows with `assigned_timeframe` 'H' are evaluated.
    - If `evaluate_daily` is True, rows with `assigned_timeframe` 'D' are evaluated.
    - Uses `last_close` and `ma_value` from the snapshot row; if either is
      missing the decision is recorded as `Skip` with reason `insufficient_data`.

    Appends each decision to the signals log via `append_signal` and returns
    the list of appended entries.
    """
    out: List[Dict[str, Any]] = []
    for row in rows:
        tf = (row.get("assigned_timeframe") or "").strip().upper()
        should_eval = (evaluate_hourly and tf == "H") or (evaluate_daily and tf == "D")
        if not should_eval:
            continue

        last_close = row.get("last_close")
        ma_value = row.get("ma_value")
        if last_close is None or ma_value is None:
            e = _make_entry_from_row(row, "Skip")
            e["reason"] = "insufficient_data"
            e["action"] = "simulate" if dry_run else "live"
            append_signal(e)
            out.append(e)
            continue

        try:
            close_f = float(last_close)
            ma_f = float(ma_value)
        except Exception:
            e = _make_entry_from_row(row, "Skip")
            e["reason"] = "invalid_values"
            e["action"] = "simulate" if dry_run else "live"
            append_signal(e)
            out.append(e)
            continue

        # New requirement: only emit SellSignal when price closed below MA
        # AND the snapshot row's `abv_be` flag is True (safety gate)
        abv_be_flag = row.get('abv_be')
        try:
            abv_be = bool(abv_be_flag)
        except Exception:
            abv_be = False

        if close_f < ma_f and abv_be:
            dec = "SellSignal"
        else:
            dec = "NoSignal"

        entry = _make_entry_from_row(row, dec)
        entry["action"] = "simulate" if dry_run else "live"
        append_signal(entry)
        out.append(entry)

    return out


def generate_signals_from_latest_snapshot(evaluate_hourly: bool = True, evaluate_daily: bool = False, dry_run: bool = True) -> List[Dict[str, Any]]:
    rows = read_latest_minute_snapshot()
    return generate_signals_from_rows(rows, evaluate_hourly=evaluate_hourly, evaluate_daily=evaluate_daily, dry_run=dry_run)


