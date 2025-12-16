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

    # Ensure oldest-first ordering for deterministic grouping (use datetimes, not string compare)
    bars = list(halfhours)
    try:
        d0s = bars[0].get("Date") if bars else None
        d1s = bars[-1].get("Date") if bars else None
        d0 = _dt.fromisoformat(str(d0s)) if d0s else None
        d1 = _dt.fromisoformat(str(d1s)) if d1s else None
        if d0 and d1 and d0 > d1:
            bars = list(reversed(bars))
    except Exception:
        # best-effort: if parsing fails, fall back to original order
        pass

    # Group by hour-start as datetime objects for robust ordering across timezone formats
    groups: Dict[_dt, List[Dict[str, Any]]] = {}
    for b in bars:
        d = b.get("Date")
        if not d:
            continue
        try:
            bdt = _dt.fromisoformat(str(d))
            hour_start = bdt.replace(minute=0, second=0, microsecond=0)
            groups.setdefault(hour_start, []).append(b)
        except Exception:
            # Fallback: try a coarse string-derived key (least-preferred)
            try:
                # create a naive hour-start string as fallback
                key_str = str(d)[:13] + ":00:00"
                # skip grouping by string when possible (we keep only datetime groups above)
                # convert fallback string into a naive datetime if possible
                try:
                    fallback_dt = _dt.fromisoformat(key_str)
                    groups.setdefault(fallback_dt, []).append(b)
                except Exception:
                    continue
            except Exception:
                continue

    hourly: List[Dict[str, Any]] = []
    # iterate groups in chronological order
    for hour_dt, items in sorted(groups.items(), key=lambda x: x[0]):
        # sort items by parsed Date ascending within the hour
        try:
            items = sorted(items, key=lambda x: _dt.fromisoformat(str(x.get("Date"))))
        except Exception:
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
                "Date": hour_dt.isoformat(),
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


