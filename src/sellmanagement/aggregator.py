from typing import List, Dict, Any
from datetime import datetime
from .cache import load_bars, write_bars, persist_bars
from .trace import append_halfhour_trace


def halfhours_to_hours(halfhour_bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate 30m bars into hourly OHLCV.

    Expects `halfhour_bars` ordered oldest->newest.
    Returns hourly bars ordered oldest->newest.
    Each bar is a dict with keys: Date, Open, High, Low, Close, Volume
    """
    if not halfhour_bars:
        return []

    # Parse dates robustly, dedupe exact timestamps, and sort by datetime
    parsed: List[tuple[datetime, Dict[str, Any]]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    dup_count = 0
    for b in halfhour_bars:
        d = b.get('Date')
        if d is None:
            continue
        s = str(d)
        # keep last occurrence for a given exact timestamp
        seen[s] = b

    for s, b in seen.items():
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            # try trimming timezone offset if present, fallback to parsing up to minute
            try:
                dt = datetime.fromisoformat(s[:19])
            except Exception:
                # last resort: parse year-month-day hour:minute by slicing
                try:
                    dt = datetime.fromisoformat(s[:16] + ":00")
                except Exception:
                    # skip unparsable entries
                    continue
        parsed.append((dt, b))

    # sort by datetime ascending
    parsed.sort(key=lambda t: t[0])

    # group by hour
    groups: Dict[datetime, List[Dict[str, Any]]] = {}
    for dt, b in parsed:
        hour_dt = dt.replace(minute=0, second=0, microsecond=0)
        groups.setdefault(hour_dt, []).append(b)

    keys = sorted(groups.keys())
    out: List[Dict[str, Any]] = []
    for k in keys:
        bucket = groups[k]
        if not bucket:
            continue
        opens = [float(x.get('Open') or 0.0) for x in bucket]
        highs = [float(x.get('High') or 0.0) for x in bucket]
        lows = [float(x.get('Low') or 0.0) for x in bucket]
        closes = [float(x.get('Close') or 0.0) for x in bucket]
        volumes = [float(x.get('Volume') or 0.0) for x in bucket]
        hour_bar = {
            'Date': k.isoformat(),
            'Open': opens[0],
            'High': max(highs) if highs else None,
            'Low': min(lows) if lows else None,
            'Close': closes[-1] if closes else None,
            'Volume': sum(volumes),
        }
        out.append(hour_bar)
    return out


def aggregate_and_persist_to_hour(key_halfhour: str, key_hour: str) -> None:
    """Load half-hour cache for `key_halfhour`, aggregate to hours and persist to `key_hour`.

    Keys are in cache.key format `EXCHANGE:SYM:30m` and `EXCHANGE:SYM:1h`.
    """
    hh = load_bars(key_halfhour, limit=None)
    try:
        append_halfhour_trace({"event": "aggregate_start", "halfhour_key": key_halfhour, "halfhour_count": len(hh)})
    except Exception:
        pass
    hours = halfhours_to_hours(hh)
    if hours:
        # compute some diagnostics
        try:
            sample_dates = [b.get('Date') for b in hh[:5]] + [b.get('Date') for b in hh[-5:]]
        except Exception:
            sample_dates = []
        unique_hours = len(hours)
        try:
            append_halfhour_trace({"event": "aggregate_diagnostics", "halfhour_key": key_halfhour, "halfhour_count": len(hh), "unique_hour_count": unique_hours, "sample_dates": sample_dates[:10]})
        except Exception:
            pass

        # replace hourly cache with aggregated bars
        write_bars(key_hour, hours)
        try:
            append_halfhour_trace({"event": "aggregate_done", "halfhour_key": key_halfhour, "hour_key": key_hour, "hour_count": unique_hours})
        except Exception:
            pass

