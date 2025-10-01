"""Helpers to aggregate 30-minute bars into hourly bars.

These functions are intentionally small and testable.
"""
from typing import List, Dict, Any


def aggregate_halfhours_to_hours(halfhours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate 30-minute bars (assumed newest-last) into hourly bars.

    The function groups pairs of consecutive halfhour bars into one hourly bar.
    If an odd number of halfhours exists, the last unmatched halfhour is dropped.

    Input bar dicts must contain at least: Date, Open, High, Low, Close, Volume.
    Returns hourly bars in newest-last order.
    """
    if not halfhours:
        return []

    # ensure oldest-first ordering for grouping
    bars = list(halfhours)

    # if they are newest-last, reverse to oldest-first for pairing
    # detect by comparing first/last Date strings: assume chronological if Date increases
    try:
        if bars[0].get("Date") and bars[-1].get("Date") and bars[0]["Date"] > bars[-1]["Date"]:
            bars = list(reversed(bars))
    except Exception:
        # if Date comparison fails, proceed with given order
        pass

    hourly: List[Dict[str, Any]] = []
    i = 0
    while i + 1 < len(bars):
        a = bars[i]
        b = bars[i + 1]
        try:
            hour_bar = {
                "Date": b.get("Date"),
                "Open": a.get("Open"),
                "High": max(a.get("High", 0) or 0, b.get("High", 0) or 0),
                "Low": min(a.get("Low", 0) or 0, b.get("Low", 0) or 0),
                "Close": b.get("Close"),
                "Volume": (a.get("Volume", 0) or 0) + (b.get("Volume", 0) or 0),
            }
            hourly.append(hour_bar)
        except Exception:
            # skip malformed pair
            pass
        i += 2

    # return newest-last ordering
    return hourly


