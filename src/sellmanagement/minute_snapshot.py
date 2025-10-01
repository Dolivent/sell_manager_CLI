from datetime import datetime
from zoneinfo import ZoneInfo
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from .assign import get_assignments_list
from .cache import merge_bars, _key_to_path, load_bars
from .downloader import batch_download_daily, backfill_halfhours_sequential
from .aggregation import aggregate_halfhours_to_hours
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


def run_minute_snapshot(ib_client, tickers: List[str], concurrency: int = 32) -> (str, List[Dict[str, Any]]):
    """Run a minute snapshot:

    - Download last 7 days of daily bars for provided tickers
    - Merge into local cache (replace by Date)
    - Compute assigned MA value and the latest close
    - Append per-ticker row into `logs/minute_snapshot.jsonl`

    Returns the path to the log file.
    """

    # use America/New_York timezone for all snapshot timestamps
    ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    append_trace({"event": "minute_snapshot_start", "tickers": tickers, "ts": ts})

    snap_start = time.perf_counter()

    # load assignments in file order and partition tickers by assigned timeframe
    assignments = {r.get('ticker'): r for r in get_assignments_list()}
    daily_tickers: List[str] = []
    hourly_tickers: List[str] = []
    for tk in tickers:
        ass = assignments.get(tk)
        tf = (ass.get('timeframe') if ass else '1H') or '1H'
        if tf.strip().upper() in ("1H", "H", "HOURLY"):
            hourly_tickers.append(tk)
        else:
            daily_tickers.append(tk)

    # download a reduced short duration for daily-assigned tickers only (2 days)
    results: Dict[str, List[Dict[str, Any]]] = {}
    # rows collects per-ticker snapshot rows
    rows: List[Dict[str, Any]] = []
    if daily_tickers:
        batch_submitted_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
        t0 = time.perf_counter()
        results = batch_download_daily(ib_client, daily_tickers, batch_size=concurrency, batch_delay=0, duration="2 D")
        t1 = time.perf_counter()
        batch_returned_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
        append_trace({
            "event": "batch_download_daily_done",
            "tickers": daily_tickers,
            "submitted_ts": batch_submitted_ts,
            "returned_ts": batch_returned_ts,
            "duration_ms": (t1 - t0) * 1000.0,
            "count": len(results),
        })

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
                # For minute snapshot request only a short recent window. Measure download time.
                try:
                    download_submitted_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
                    dl0 = time.perf_counter()
                    halfhours = ib_client.download_halfhours(tk, duration="1 D") or []
                    dl1 = time.perf_counter()
                    download_returned_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
                    per_dl_ms = (dl1 - dl0) * 1000.0
                except Exception:
                    download_submitted_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
                    bf0 = time.perf_counter()
                    halfhours = backfill_halfhours_sequential(ib_client, tk, target_bars=4)
                    bf1 = time.perf_counter()
                    download_returned_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
                    per_dl_ms = (bf1 - bf0) * 1000.0
                # record per-ticker download time and submitted/returned timestamps in trace
                append_trace({
                    "event": "halfhours_download_done",
                    "token": tk,
                    "download_ms": per_dl_ms,
                    "count": len(halfhours),
                    "submitted_ts": download_submitted_ts,
                    "returned_ts": download_returned_ts,
                })

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
        # determine the chosen bar (prefer the closed bar preceding the snapshot)
        last_close = None
        last_bar_date = None
        try:
            # snapshot ts is `ts` (NY ISO)
            from datetime import datetime as _dt
            try:
                snap_dt = _dt.fromisoformat(ts)
            except Exception:
                snap_dt = None

            chosen = None
            if bars:
                # parse bar dates and find the latest bar whose datetime <= snapshot
                candidates = []
                last_bar = None
                for b in bars:
                    bd = b.get("Date")
                    if not bd:
                        continue
                    try:
                        bdt = _dt.fromisoformat(str(bd))
                    except Exception:
                        bdt = None
                    if bdt is None:
                        continue
                    last_bar = b
                    # if snapshot time available and bar time <= snapshot, consider it
                    if snap_dt is not None and bdt <= snap_dt:
                        candidates.append((bdt, b))

                if candidates:
                    # choose the candidate with the latest datetime
                    candidates.sort(key=lambda x: x[0])
                    chosen = candidates[-1][1]
                else:
                    # no candidate <= snapshot (e.g., pre-market with future-dated bars missing)
                    # choose the last available bar (most recent) -- this is the safe fallback
                    chosen = last_bar if last_bar is not None else (bars[-1] if bars else None)

            if chosen:
                # For daily timeframe: if snapshot is before market open (09:30 NY)
                # and IB returned a same-day daily row, prefer previous day's row.
                try:
                    if tf.strip().upper() not in ("1H", "H", "HOURLY"):
                        try:
                            # chosen.get('Date') is like 'YYYY-MM-DD'
                            from datetime import date as _date
                            bar_date_str = str(chosen.get('Date'))
                            bar_date = _dt.fromisoformat(bar_date_str).date()
                            snap_date = snap_dt.date() if snap_dt is not None else None
                            if snap_date is not None and bar_date == snap_date:
                                # only prefer previous-day when before market open (09:30)
                                before_open = (snap_dt.hour < 9) or (snap_dt.hour == 9 and snap_dt.minute < 30)
                                if before_open:
                                    prev_daily = [b for b in bars if str(b.get('Date')) != bar_date_str]
                                    if prev_daily:
                                        chosen = prev_daily[-1]
                        except Exception:
                            # non-ISO or unexpected date string; ignore and continue
                            pass
                except Exception:
                    pass

                try:
                    last_close = float(chosen.get('Close')) if chosen.get('Close') is not None else None
                except Exception:
                    last_close = None
                last_bar_date = chosen.get('Date')
        except Exception:
            last_close = closes[-1] if closes else None
            last_bar_date = bars[-1].get('Date') if bars else None

        # compute MA only when assignment exists and has valid type/length
        if ass and bars:
            # defensive: ensure type and length are present and valid
            try:
                ttype = (ass.get('type') or '').strip().upper()
                l = int(ass.get('length') or 0)
            except Exception:
                # malformed assignment; skip MA computation for this ticker
                append_trace({"event": "invalid_assignment_skip", "token": tk, "assignment": ass})
                ttype = ''
                l = 0
            tf = (ass.get('timeframe') or '1H').strip().upper()
            if not ttype or l <= 0:
                # user hasn't assigned a proper MA yet; skip computation
                ma_value = None
            else:
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
            "last_bar_date": last_bar_date,
            "distance_pct": None if distance_pct is None else float(distance_pct),
        }
        rows.append(row)

    # append everything into one log record per minute (array of rows)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "rows": rows}, ensure_ascii=False) + "\n")

    append_trace({"event": "minute_snapshot_done", "tickers": tickers, "count": len(rows)})
    # return timestamp (ISO NY) and rows so callers can trigger downstream flows
    return ts, rows


