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
    start_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    append_trace({"event": "minute_snapshot_start", "tickers": tickers, "start_ts": start_ts})

    snap_start = time.perf_counter()

    # Fetch current open orders and live positions to enrich snapshot rows (best-effort)
    try:
        open_orders_raw = ib_client.openOrders() or []
    except Exception:
        open_orders_raw = []

    try:
        live_positions_raw = ib_client.positions() or []
    except Exception:
        live_positions_raw = []

    # Build a mapping ticker -> avgCost from live positions
    pos_avg_map = {}
    for p in (live_positions_raw or []):
        try:
            contract = getattr(p, 'contract', None) if not isinstance(p, dict) else p.get('contract')
            if contract is None:
                continue
            symbol = getattr(contract, 'symbol', None) if not isinstance(contract, dict) else contract.get('symbol')
            exchange = getattr(contract, 'exchange', None) if not isinstance(contract, dict) else contract.get('exchange')
            if not symbol:
                continue
            token = f"{exchange or 'SMART'}:{symbol}"
            avg_cost = getattr(p, 'avgCost', None) if not isinstance(p, dict) else p.get('avgCost')
            try:
                pos_avg_map[token] = float(avg_cost) if avg_cost is not None else None
            except Exception:
                pos_avg_map[token] = None
        except Exception:
            continue

    # Build a mapping ticker -> list of stop prices from open orders (best-effort matching)
    orders_map = {}
    def _get_attr(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    import re

    ticker_re = re.compile(r"([A-Za-z]{1,6}:[A-Za-z0-9\.-_]{1,12})")
    for o in (open_orders_raw or []):
        try:
            raw = o
            # Support cases where openOrders returns tuples like (order, orderState, contract)
            parts = []
            if isinstance(raw, (list, tuple)):
                parts = list(raw)
            else:
                parts = [raw]

            # try to find contract-like and order-like pieces inside the parts
            contract_obj = None
            order_obj = None
            for part in parts:
                if part is None:
                    continue
                # detect contract by symbol/exchange
                if _get_attr(part, 'symbol') or (isinstance(part, dict) and part.get('symbol')):
                    contract_obj = part
                # detect order-like by presence of common order fields
                if any(_get_attr(part, f) is not None for f in ('auxPrice', 'trailStopPrice', 'triggerPrice', 'stopPrice')):
                    order_obj = part

            token = None
            if contract_obj:
                csym = _get_attr(contract_obj, 'symbol') if not isinstance(contract_obj, dict) else contract_obj.get('symbol')
                cex = _get_attr(contract_obj, 'exchange') if not isinstance(contract_obj, dict) else contract_obj.get('exchange')
                if csym:
                    token = f"{cex or 'SMART'}:{csym}"

            # fallback: inspect textual fields like ocaGroup/orderRef across all parts
            if token is None:
                for part in parts:
                    for field in ('ocaGroup', 'orderRef'):
                        fv = _get_attr(part, field) or ''
                        if not fv:
                            continue
                        # first try regex to extract EXCHANGE:SYMBOL pattern
                        m = ticker_re.search(str(fv))
                        if m:
                            token = m.group(1)
                            break
                        # fallback: search for any assigned ticker symbol inside the string
                        for tk in (tickers or []):
                            if tk in str(fv):
                                token = tk
                                break
                        if token:
                            break
                    if token:
                        break

            # extract stop price candidates from order_obj first, then top-level
            stop_price = None
            candidates = []
            if order_obj is not None:
                for f in ('auxPrice', 'trailStopPrice', 'triggerPrice', 'stopPrice'):
                    v = _get_attr(order_obj, f)
                    if v is not None:
                        candidates.append(v)
            # also check top-level raw object for fields
            for f in ('auxPrice', 'trailStopPrice', 'triggerPrice', 'stopPrice'):
                v = _get_attr(raw, f)
                if v is not None:
                    candidates.append(v)

            for v in candidates:
                try:
                    sp = float(v)
                    # skip sentinel large values used by IB to indicate not-set
                    if sp > 1e10:
                        continue
                    stop_price = sp
                    break
                except Exception:
                    continue

            if token and stop_price is not None:
                orders_map.setdefault(token, []).append(stop_price)
        except Exception:
            continue

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

                # persist recent halfhours into 30m cache, then aggregate full 30m -> 1h
                try:
                    key30 = f"{tk}:30m"
                    # merge new halfhour slice into 30m cache so cache stays current
                    try:
                        merge_bars(key30, halfhours)
                    except Exception:
                        append_trace({"event": "merge_30m_from_snapshot_failed", "token": tk})

                    # load full 30m cache and aggregate to hourly
                    try:
                        full_halfhours = load_bars(key30)
                        hourly = aggregate_halfhours_to_hours(full_halfhours)
                    except Exception:
                        # fallback: aggregate from the downloaded slice if cache load fails
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
            # snapshot ts is `start_ts` (NY ISO)
            from datetime import datetime as _dt
            try:
                snap_dt = _dt.fromisoformat(start_ts)
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
            "ts": start_ts,
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

        # compute 'abv_be' per requested change: true if
        #  - last_close > avgCost for the position AND
        #  - ma_value > avgCost for the position
        try:
            abv = False
            avg_for_pos = pos_avg_map.get(tk)
            last_cl = row.get('last_close')
            ma_val = row.get('ma_value')
            if avg_for_pos is not None and last_cl is not None and ma_val is not None:
                try:
                    if float(last_cl) > float(avg_for_pos) and float(ma_val) > float(avg_for_pos):
                        abv = True
                except Exception:
                    abv = False
            row['abv_be'] = bool(abv)
        except Exception:
            row['abv_be'] = False
        rows.append(row)

    # append everything into one log record per minute (array of rows)
    # capture end timestamp (when processing finished) for caller display
    end_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        # preserve previous field name for compatibility but include both timestamps
        f.write(json.dumps({"start_ts": start_ts, "end_ts": end_ts, "rows": rows}, ensure_ascii=False) + "\n")

    append_trace({"event": "minute_snapshot_done", "tickers": tickers, "count": len(rows), "end_ts": end_ts})
    # return end timestamp (ISO NY) and rows so callers can display the completion time
    return end_ts, rows


