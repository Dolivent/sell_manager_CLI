"""Helpers to aggregate 30-minute bars into hourly bars.

These functions are intentionally small and testable.
"""
from typing import List, Dict, Any
from datetime import datetime as _dt


def aggregate_halfhours_to_hours(halfhours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate 30-minute bars (assumed newest-last) into hourly bars.

    Robust approach: group halfhours by the hour start timestamp derived from each
    bar's Date (set minutes/seconds to zero), then compute Open/High/Low/Close/Volume
    for each hour. Labels the hourly bar with the hour start (e.g., 15:00 for 15:00–16:00).

    Input bar dicts must contain at least: Date, Open, High, Low, Close, Volume.
    Returns hourly bars in newest-last order.
    """
    if not halfhours:
        return []

    # Ensure oldest-first ordering for deterministic grouping
    bars = list(halfhours)
    try:
        d0 = bars[0].get("Date")
        d1 = bars[-1].get("Date")
        if d0 and d1 and str(d0) > str(d1):
            bars = list(reversed(bars))
    except Exception:
        pass

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for b in bars:
        d = b.get("Date")
        if not d:
            continue
        try:
            bdt = _dt.fromisoformat(str(d))
            hour_start = bdt.replace(minute=0, second=0, microsecond=0)
            key = hour_start.isoformat()
        except Exception:
            # Fallback: derive key by truncating the string (unsafe but better than dropping)
            try:
                key = str(d)[:13] + ":00:00"
            except Exception:
                continue
        groups.setdefault(key, []).append(b)

    hourly: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        items = groups[key]
        # sort items by Date ascending within the hour
        try:
            items = sorted(items, key=lambda x: str(x.get("Date")))
        except Exception:
            pass
        try:
            open_v = items[0].get("Open")
            close_v = items[-1].get("Close")
            high_v = max((it.get("High") or 0) for it in items)
            low_v = min((it.get("Low") or 0) for it in items)
            vol_v = 0
            for it in items:
                try:
                    vol_v += int(it.get("Volume") or 0)
                except Exception:
                    pass
            hour_bar = {
                "Date": key,
                "Open": open_v,
                "High": high_v,
                "Low": low_v,
                "Close": close_v,
                "Volume": vol_v,
            }
            hourly.append(hour_bar)
        except Exception:
            # skip malformed hour group
            continue

    return hourly


