from datetime import datetime
import json
from pathlib import Path
from typing import List, Dict, Any

from .assign import get_assignments_list
from .cache import merge_bars, _key_to_path, load_bars
from .downloader import batch_download_daily, backfill_halfhours_sequential
from .trace import append_trace
from .indicators import compute_sma_series_all, compute_ema_series_all


LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "minute_snapshot.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _make_key_from_ticker(ticker: str, timeframe: str = "1D") -> str:
    # ticker already in EXCHANGE:SYM format; cache key uses granularity suffix
    tf = (timeframe or "1D").strip().upper()
    if tf in ("1H", "H", "HOURLY"):
        gran = "1h"
    else:
        gran = "1d"
    return f"{ticker}:{gran}"


def run_minute_snapshot(ib_client, tickers: List[str], concurrency: int = 32) -> List[Dict[str, Any]]:
    """Run a minute snapshot:

    - Download last 7 days of daily bars for provided tickers
    - Merge into local cache (replace by Date)
    - Compute assigned MA value and the latest close
    - Append per-ticker row into `logs/minute_snapshot.jsonl`

    Returns the path to the log file.
    """
    ts = datetime.utcnow().isoformat()
    append_trace({"event": "minute_snapshot_start", "tickers": tickers, "ts": ts})

    # download short duration (7 D) for daily cache only
    results = batch_download_daily(ib_client, tickers, batch_size=concurrency, batch_delay=0, duration="7 D")

    rows: List[Dict[str, Any]] = []
    # load assignments in file order
    assignments = {r.get('ticker'): r for r in get_assignments_list()}

    for tk in tickers:
        ass = assignments.get(tk, None)
        timeframe = (ass.get('timeframe') if ass else '1H') or '1H'

        # if assignment is hourly, do NOT compute MA from daily data; require hourly cache
        if timeframe.strip().upper() in ("1H", "H", "HOURLY"):
            key = _make_key_from_ticker(tk, timeframe="1H")
            # For hourly-assigned tickers we fetch a short 30m snapshot and
            # aggregate to hourly. We avoid backfilling here (minute snapshot)
            # and instead request a single 31-bar slice for efficiency.
            try:
                halfhours = []
                # try to call ib_client download helper with 31-day window
                # the downloader helper returns newest-last; tests expect list
                try:
                    halfhours = ib_client.download_halfhours(tk, duration="31 D") or []
                except Exception:
                    # fallback to backfill helper if available (shouldn't be used in minute path)
                    halfhours = backfill_halfhours_sequential(ib_client, tk, target_bars=31)

                # convert to hourly bars using aggregator and persist
                try:
                    hourly = aggregate_halfhours_to_hours(halfhours)
                    if hourly:
                        merge_bars(key, hourly)
                except Exception:
                    append_trace({"event": "aggregate_or_merge_failed", "token": tk})
                bars = load_bars(key, limit=365)
            except Exception:
                bars = load_bars(key, limit=365)
        else:
            # daily timeframe: merge downloaded daily bars and load daily cache
            key = _make_key_from_ticker(tk, timeframe="1D")
            new_bars = results.get(tk, [])
            if new_bars:
                try:
                    merge_bars(key, new_bars)
                except Exception:
                    append_trace({"event": "merge_failed", "token": tk})
            bars = load_bars(key, limit=365)
        closes: List[float] = []
        for b in bars:
            try:
                c = b.get('Close')
                closes.append(float(c) if c is not None else 0.0)
            except Exception:
                closes.append(0.0)

        # defaults
        ma_value = None
        distance_pct = None
        last_close = closes[-1] if closes else None

        # compute MA only when assignment timeframe exists in the corresponding cache
        if ass and bars:
            l = int(ass.get('length', 0))
            ttype = ass.get('type', 'SMA')
            tf = (ass.get('timeframe') or '1H').strip().upper()
            # if assignment is hourly but no hourly bars exist, skip computation (mark missing)
            if tf in ("1H", "H", "HOURLY") and not bars:
                ma_value = None
            else:
                if ttype == 'SMA':
                    sma_map = compute_sma_series_all(closes, [l])
                    series = sma_map.get(l, [])
                    ma_value = series[-1] if series else None
                else:
                    ema_map = compute_ema_series_all(closes, [l])
                    series = ema_map.get(l, [])
                    ma_value = series[-1] if series else None
                if ma_value is not None and last_close is not None:
                    try:
                        distance_pct = ((last_close - ma_value) / ma_value) * 100.0 if ma_value != 0 else None
                    except Exception:
                        distance_pct = None

        tf_display = None
        if ass:
            tf = (ass.get('timeframe') or '1H').strip().upper()
            tf_display = 'H' if tf in ("1H", "H", "HOURLY") else 'D'

        row = {
            "ts": ts,
            "ticker": tk,
            "assigned_type": ass.get('type') if ass else None,
            "assigned_length": int(ass.get('length')) if ass else None,
            "assigned_timeframe": tf_display,
            "assigned_ma": f"{ass.get('type') or ''}({ass.get('length') or ''})" if ass else None,
            "ma_value": None if ma_value is None else float(ma_value),
            "last_close": None if last_close is None else float(last_close),
            "distance_pct": None if distance_pct is None else float(distance_pct),
        }
        rows.append(row)

    # append everything into one log record per minute (array of rows)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "rows": rows}, ensure_ascii=False) + "\n")

    append_trace({"event": "minute_snapshot_done", "tickers": tickers, "count": len(rows)})
    return rows


