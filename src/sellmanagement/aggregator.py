from typing import List, Dict, Any
from datetime import datetime
from .cache import load_bars, write_bars, persist_bars


def halfhours_to_hours(halfhour_bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate 30m bars into hourly OHLCV.

    Expects `halfhour_bars` ordered oldest->newest.
    Returns hourly bars ordered oldest->newest.
    Each bar is a dict with keys: Date, Open, High, Low, Close, Volume
    """
    if not halfhour_bars:
        return []

    # group by hour key based on Date string; assume Date is ISO-like or comparable
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for b in halfhour_bars:
        d = b.get('Date')
        if d is None:
            continue
        try:
            dt = datetime.fromisoformat(str(d))
        except Exception:
            # fallback: use string prefix up to hour
            key = str(d)[:13]
        else:
            key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        groups.setdefault(key, []).append(b)

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
            'Date': k,
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
    hours = halfhours_to_hours(hh)
    if hours:
        # replace hourly cache with aggregated bars
        write_bars(key_hour, hours)

