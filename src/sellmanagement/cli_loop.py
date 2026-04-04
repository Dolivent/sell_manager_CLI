"""CLI minute-loop helpers (sleep alignment, snapshot table)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def read_last_signal_batch(log_path: Path) -> List[Dict[str, Any]]:
    """Return signal dicts from the newest second-bucket in an NDJSON log."""
    if not log_path.exists():
        return []
    groups: Dict[str, List[Dict[str, Any]]] = {}
    last_key: str | None = None
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            ts = obj.get("ts")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts)
                key = dt.replace(microsecond=0).isoformat()
            except Exception:
                key = ts.split(".")[0] if "." in ts else ts
            groups.setdefault(key, []).append(obj)
            last_key = key
    if not last_key:
        return []
    return groups.get(last_key, [])


def print_last_signals_preview(log_path: Path) -> None:
    """Print the most recent signal batch for startup visibility."""
    last_batch = read_last_signal_batch(log_path)
    if not last_batch:
        return
    print("\nLast signals (most recent batch):")
    for s in last_batch:
        try:
            print(f"{s.get('ticker', '<unknown>'):20} -> {s.get('decision', '<undecided>')}")
        except Exception:
            continue


def sleep_until_next_minute_ny(
    *,
    max_chunk_seconds: float = 5.0,
    time_sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Sleep until the next minute boundary in America/New_York (chunked for Ctrl+C).

    Wakes ~5 seconds early before 16:00 NY (session end) to match prior behaviour.
    """
    now = datetime.now(tz=NY)
    next_min = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if next_min.hour == 16 and next_min.minute == 0:
        seconds_till_next = (next_min - now).total_seconds() - 5.0
    else:
        seconds_till_next = (next_min - now).total_seconds()
    if seconds_till_next < 0.1:
        seconds_till_next = 0.1

    slept = 0.0
    chunk = min(max_chunk_seconds, seconds_till_next)
    while slept + 0.0001 < seconds_till_next:
        to_sleep = min(chunk, seconds_till_next - slept)
        time_sleep(to_sleep)
        slept += to_sleep


def heartbeat_cycle(
    last_wake: datetime | None,
    append_trace: Callable[[dict], None],
    *,
    heartbeat_interval: float = 60.0,
    now_fn: Callable[[], datetime] | None = None,
) -> datetime:
    """Detect long gaps, append ``woke_late`` if needed; return new ``last_wake`` time."""
    _now = now_fn or (lambda: datetime.now(tz=NY))
    woke_at = _now()
    if last_wake is None:
        return woke_at
    gap = (woke_at - last_wake).total_seconds()
    if gap > (heartbeat_interval * 1.5):
        try:
            append_trace(
                {
                    "event": "woke_late",
                    "gap_seconds": gap,
                    "reason": "suspiciously_large_gap",
                }
            )
        except Exception:
            pass
    return woke_at


def sort_snapshot_rows_for_display(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort rows: ``abv_be`` True first, then ``distance_pct`` ascending."""

    def _sort_key(r: Dict[str, Any]):
        abv_key = not bool(r.get("abv_be"))
        dist = r.get("distance_pct")
        try:
            dist_key = float(dist) if dist is not None else float("inf")
        except Exception:
            dist_key = float("inf")
        return (abv_key, dist_key)

    try:
        return sorted(rows, key=_sort_key)
    except Exception:
        return rows


def print_snapshot_table(rows: List[Dict[str, Any]]) -> None:
    """Print aligned snapshot columns to stdout."""
    hdr = f"{'ticker':20}{'last_close':>12}{'ma_value':>12}{'distance_pct':>14}  {'assigned_ma':>18}{'abv_be':>8}"
    print(hdr)
    for r in rows:
        tk = r.get("ticker") or ""
        last_close = r.get("last_close")
        ma_value = r.get("ma_value")
        distance = r.get("distance_pct")

        if last_close is None:
            last_s = "-"
        else:
            try:
                last_s = f"{float(last_close):.2f}"
            except Exception:
                last_s = str(last_close)

        if ma_value is None:
            ma_s = "-"
        else:
            try:
                ma_s = f"{float(ma_value):.2f}"
            except Exception:
                ma_s = str(ma_value)

        if distance is None:
            dist_s = "-"
        else:
            try:
                dist_s = f"{float(distance):.1f}%"
            except Exception:
                dist_s = str(distance)

        am = r.get("assigned_ma") or "-"
        tf = r.get("assigned_timeframe") or "-"
        assigned_display = f"{tf} {am}" if am and tf else (am or "-")
        abv_be_val = r.get("abv_be")
        if abv_be_val is None:
            abv_s = "-"
        else:
            abv_s = "T" if bool(abv_be_val) else "F"
        print(f"{tk:20}{last_s:>12}{ma_s:>12}{dist_s:>14}  {assigned_display:>18}{abv_s:>8}")
