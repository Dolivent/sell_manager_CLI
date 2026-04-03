from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from .assign import get_assignments_list
from .cache import merge_bars, load_bars
from .downloader import batch_download_daily, backfill_halfhours_sequential
from .aggregation import aggregate_halfhours_to_hours
from .trace import append_trace
from .indicators import compute_sma_series_all, compute_ema_series_all


LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "minute_snapshot.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SnapshotRow:
    ticker: str
    assigned_type: Optional[str]
    assigned_length: Optional[int]
    assigned_timeframe: Optional[str]
    ma_value: Optional[float]
    last_close: Optional[float]
    distance_pct: Optional[float]
    position: float
    avg_cost: Optional[float]
    abv_be: bool
    ts: str
    last_bar_date: Optional[str]
    assigned_ma: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "ticker": self.ticker,
            "assigned_type": self.assigned_type,
            "assigned_length": self.assigned_length,
            "assigned_timeframe": self.assigned_timeframe,
            "assigned_ma": self.assigned_ma,
            "ma_value": self.ma_value,
            "last_close": self.last_close,
            "last_bar_date": self.last_bar_date,
            "distance_pct": self.distance_pct,
            "position": self.position,
            "avg_cost": self.avg_cost,
            "abv_be": self.abv_be,
        }


@dataclass
class SnapshotContext:
    ib_client: Any
    tickers: List[str]
    assignments: Dict[str, Dict[str, Any]]
    live_positions_raw: List[Any] = field(default_factory=list)
    open_orders_raw: List[Any] = field(default_factory=list)
    pos_avg_map: Dict[str, Optional[float]] = field(default_factory=dict)
    pos_size_map: Dict[str, float] = field(default_factory=dict)
    orders_map: Dict[str, List[float]] = field(default_factory=dict)
    daily_tickers: List[str] = field(default_factory=list)
    hourly_tickers: List[str] = field(default_factory=list)
    daily_results: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    start_ts: str = ""
    snap_dt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_key_from_ticker(ticker: str, timeframe: str = "1D") -> str:
    tf = (timeframe or "1D").strip().upper()
    gran = "1h" if tf in ("1H", "H", "HOURLY") else "1d"
    return f"{ticker}:{gran}"


def _get_attr(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


# ---------------------------------------------------------------------------
# Phase 1: Build context
# ---------------------------------------------------------------------------

def _build_context(ib_client, tickers: List[str]) -> SnapshotContext:
    start_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    snap_dt = None
    try:
        snap_dt = datetime.fromisoformat(start_ts)
        if snap_dt.tzinfo is None:
            snap_dt = snap_dt.replace(tzinfo=ZoneInfo("America/New_York"))
    except Exception:
        snap_dt = None

    append_trace({"event": "minute_snapshot_start", "tickers": tickers, "start_ts": start_ts})

    try:
        open_orders_raw = ib_client.openOrders() or []
    except Exception:
        open_orders_raw = []

    try:
        live_positions_raw = ib_client.positions() or []
    except Exception:
        live_positions_raw = []

    assignments = {r.get("ticker"): r for r in get_assignments_list()}

    daily_tickers, hourly_tickers = _partition_tickers(tickers, assignments)

    ctx = SnapshotContext(
        ib_client=ib_client,
        tickers=tickers,
        assignments=assignments,
        live_positions_raw=live_positions_raw,
        open_orders_raw=open_orders_raw,
        daily_tickers=daily_tickers,
        hourly_tickers=hourly_tickers,
        start_ts=start_ts,
        snap_dt=snap_dt,
    )

    _build_position_maps(ctx)
    _build_orders_map(ctx)

    return ctx


def _partition_tickers(tickers: List[str], assignments: Dict[str, Dict[str, Any]]) -> tuple:
    daily_tickers: List[str] = []
    hourly_tickers: List[str] = []
    for tk in tickers:
        ass = assignments.get(tk)
        tf = (ass.get("timeframe") if ass else "1H") or "1H"
        if tf.strip().upper() in ("1H", "H", "HOURLY"):
            hourly_tickers.append(tk)
        else:
            daily_tickers.append(tk)
    return daily_tickers, hourly_tickers


def _build_position_maps(ctx: SnapshotContext) -> None:
    for p in (ctx.live_positions_raw or []):
        try:
            contract = _get_attr(p, "contract") if not isinstance(p, dict) else p.get("contract")
            if contract is None:
                continue
            symbol = _get_attr(contract, "symbol") if not isinstance(contract, dict) else contract.get("symbol")
            exchange = _get_attr(contract, "exchange") if not isinstance(contract, dict) else contract.get("exchange")
            if not symbol:
                continue
            token = f"{exchange or 'SMART'}:{symbol}"
            avg_cost = _get_attr(p, "avgCost") if not isinstance(p, dict) else p.get("avgCost")
            pos_size = _get_attr(p, "position") if not isinstance(p, dict) else p.get("position")
            if pos_size is None:
                pos_size = _get_attr(p, "pos") if not isinstance(p, dict) else p.get("pos")
            try:
                ctx.pos_avg_map[token] = float(avg_cost) if avg_cost is not None else None
            except Exception:
                ctx.pos_avg_map[token] = None
            try:
                ctx.pos_size_map[token] = float(pos_size) if pos_size is not None else 0.0
            except Exception:
                ctx.pos_size_map[token] = 0.0
        except Exception:
            continue


def _build_orders_map(ctx: SnapshotContext) -> None:
    import re
    ticker_re = re.compile(r"([A-Za-z]{1,6}:[A-Za-z0-9\.-_]{1,12})")

    for o in (ctx.open_orders_raw or []):
        try:
            parts = list(o) if isinstance(o, (list, tuple)) else [o]
            contract_obj = None
            order_obj = None
            for part in parts:
                if part is None:
                    continue
                if _get_attr(part, "symbol") or (isinstance(part, dict) and part.get("symbol")):
                    contract_obj = part
                if any(_get_attr(part, f) is not None for f in ("auxPrice", "trailStopPrice", "triggerPrice", "stopPrice")):
                    order_obj = part

            token = None
            if contract_obj:
                csym = _get_attr(contract_obj, "symbol") if not isinstance(contract_obj, dict) else contract_obj.get("symbol")
                cex = _get_attr(contract_obj, "exchange") if not isinstance(contract_obj, dict) else contract_obj.get("exchange")
                if csym:
                    token = f"{cex or 'SMART'}:{csym}"

            if token is None:
                for part in parts:
                    for field_name in ("ocaGroup", "orderRef"):
                        fv = _get_attr(part, field_name) or ""
                        if not fv:
                            continue
                        m = ticker_re.search(str(fv))
                        if m:
                            token = m.group(1)
                            break
                        for tk in (ctx.tickers or []):
                            if tk in str(fv):
                                token = tk
                                break
                        if token:
                            break
                    if token:
                        break

            stop_price = None
            candidates = []
            if order_obj is not None:
                for f in ("auxPrice", "trailStopPrice", "triggerPrice", "stopPrice"):
                    v = _get_attr(order_obj, f)
                    if v is not None:
                        candidates.append(v)
            for f in ("auxPrice", "trailStopPrice", "triggerPrice", "stopPrice"):
                v = _get_attr(o, f)
                if v is not None:
                    candidates.append(v)

            for v in candidates:
                try:
                    sp = float(v)
                    if sp > 1e10:
                        continue
                    stop_price = sp
                    break
                except Exception:
                    continue

            if token and stop_price is not None:
                ctx.orders_map.setdefault(token, []).append(stop_price)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Phase 2: Fetch and cache
# ---------------------------------------------------------------------------

def _fetch_and_cache(ctx: SnapshotContext, concurrency: int = 32) -> None:
    if ctx.daily_tickers:
        t0 = time.perf_counter()
        ctx.daily_results = batch_download_daily(
            ctx.ib_client, ctx.daily_tickers,
            batch_size=concurrency, batch_delay=0, duration="2 D"
        )
        t1 = time.perf_counter()
        append_trace({
            "event": "batch_download_daily_done",
            "tickers": ctx.daily_tickers,
            "duration_ms": (t1 - t0) * 1000.0,
            "count": len(ctx.daily_results),
        })

    for tk in ctx.hourly_tickers:
        _fetch_hourly_for_ticker(ctx, tk)


def _fetch_hourly_for_ticker(ctx: SnapshotContext, tk: str) -> None:
    ass = ctx.assignments.get(tk)
    required_halfhours = _required_halfhour_bars(ass)

    halfhours = _download_halfhours(ctx.ib_client, tk, required_halfhours)

    if halfhours and len(halfhours) < required_halfhours:
        _backfill_if_insufficient(ctx, tk, halfhours, required_halfhours)

    append_trace({
        "event": "halfhours_download_done",
        "token": tk,
        "count": len(halfhours),
    })

    key30 = f"{tk}:30m"
    try:
        merge_bars(key30, halfhours)
    except Exception:
        append_trace({"event": "merge_30m_from_snapshot_failed", "token": tk})

    full_halfhours = load_bars(key30)

    fresh_ok = _check_freshness(full_halfhours, ctx)

    if not fresh_ok:
        _backfill_stale(ctx, tk, full_halfhours, required_halfhours)
        full_halfhours = load_bars(key30)

    try:
        if full_halfhours:
            hourly = aggregate_halfhours_to_hours(full_halfhours)
            if not fresh_ok:
                append_trace({
                    "event": "aggregated_from_stale_halfhours",
                    "token": tk,
                    "latest_half_dt": full_halfhours[-1].get("Date") if full_halfhours else None,
                })
        else:
            hourly = []
    except Exception:
        hourly = []

    if hourly:
        key = _make_key_from_ticker(tk, "1H")
        try:
            merge_bars(key, hourly)
        except Exception:
            append_trace({"event": "aggregate_or_merge_failed", "token": tk})


def _required_halfhour_bars(ass: Optional[Dict[str, Any]]) -> int:
    if ass is None:
        return 40
    try:
        length = int(ass.get("length") or 0)
    except Exception:
        length = 0
    if length and length > 0:
        return max(40, length * 2)
    return 40


def _download_halfhours(ib_client, tk: str, required: int) -> List[Dict[str, Any]]:
    dl0 = time.perf_counter()
    download_submitted_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    try:
        halfhours = ib_client.download_halfhours(tk, duration="1 D") or []
    except Exception:
        halfhours = backfill_halfhours_sequential(ib_client, tk, target_bars=required)
    dl1 = time.perf_counter()
    download_returned_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
    per_dl_ms = (dl1 - dl0) * 1000.0
    append_trace({
        "event": "halfhours_download_done",
        "token": tk,
        "download_ms": per_dl_ms,
        "count": len(halfhours),
        "submitted_ts": download_submitted_ts,
        "returned_ts": download_returned_ts,
    })
    return halfhours


def _backfill_if_insufficient(ctx: SnapshotContext, tk: str, halfhours: List[Dict[str, Any]], required: int) -> None:
    append_trace({
        "event": "halfhours_snapshot_insufficient",
        "token": tk,
        "have": len(halfhours),
        "need": required,
    })
    try:
        extra = backfill_halfhours_sequential(ctx.ib_client, tk, target_bars=required)
        if extra:
            halfhours = (halfhours or []) + extra
            append_trace({
                "event": "halfhours_insufficient_backfill_done",
                "token": tk,
                "added": len(extra),
                "total": len(halfhours),
            })
    except Exception:
        append_trace({"event": "halfhours_insufficient_backfill_failed", "token": tk})


def _check_freshness(full_halfhours: List[Dict[str, Any]], ctx: SnapshotContext) -> bool:
    if not full_halfhours or ctx.snap_dt is None:
        return False
    try:
        latest_bar = full_halfhours[-1]
        bd = latest_bar.get("Date")
        if not bd:
            return False
        latest_dt = datetime.fromisoformat(str(bd))
        return (ctx.snap_dt - latest_dt) <= timedelta(minutes=90)
    except Exception:
        return False


def _backfill_stale(ctx: SnapshotContext, tk: str, full_halfhours: List[Dict[str, Any]], required: int) -> None:
    append_trace({
        "event": "halfhours_stale_backfill_start",
        "token": tk,
        "need": required,
        "have": len(full_halfhours),
    })
    try:
        extra = backfill_halfhours_sequential(ctx.ib_client, tk, target_bars=required)
        if extra:
            try:
                merge_bars(f"{tk}:30m", extra)
            except Exception:
                append_trace({"event": "merge_30m_from_backfill_failed", "token": tk})
            full_halfhours = load_bars(f"{tk}:30m")
            try:
                latest_bar = full_halfhours[-1] if full_halfhours else None
                if latest_bar and ctx.snap_dt and latest_bar.get("Date"):
                    latest_dt = datetime.fromisoformat(str(latest_bar.get("Date")))
                    if (ctx.snap_dt - latest_dt) <= timedelta(minutes=90):
                        append_trace({"event": "halfhours_stale_backfill_done", "token": tk, "added": len(extra), "total": len(full_halfhours)})
                    else:
                        append_trace({"event": "halfhours_stale_backfill_failed", "token": tk, "reason": "still_stale"})
                else:
                    append_trace({"event": "halfhours_stale_backfill_failed", "token": tk, "reason": "no_bars_after_backfill"})
            except Exception:
                append_trace({"event": "halfhours_stale_backfill_failed", "token": tk, "reason": "parse_error"})
        else:
            append_trace({"event": "halfhours_stale_backfill_failed", "token": tk, "reason": "no_extra_returned"})
    except Exception:
        append_trace({"event": "halfhours_stale_backfill_failed", "token": tk, "reason": "exception"})


# ---------------------------------------------------------------------------
# Phase 3: Compute snapshot rows
# ---------------------------------------------------------------------------

def _compute_snapshot_rows(ctx: SnapshotContext) -> List[SnapshotRow]:
    rows: List[SnapshotRow] = []
    for tk in ctx.tickers:
        row = _compute_single_row(ctx, tk)
        rows.append(row)
    return rows


def _compute_single_row(ctx: SnapshotContext, tk: str) -> SnapshotRow:
    ass = ctx.assignments.get(tk)
    tf_raw = (ass.get("timeframe") if ass else "1H") or "1H"
    tf = tf_raw.strip().upper()
    is_hourly = tf in ("1H", "H", "HOURLY")

    key = _make_key_from_ticker(tk, timeframe="1D" if not is_hourly else "1H")
    bars = _load_bars_for_ticker(ctx, tk, key, is_hourly)
    closes = _extract_closes(bars)

    last_close, last_bar_date, chosen = _compute_last_close_and_bar(bars, ctx.snap_dt, is_hourly)

    ma_value, distance_pct = _compute_ma_and_distance(ass, closes, last_close)

    avg_for_pos = ctx.pos_avg_map.get(tk)
    last_cl = last_close
    ma_val = ma_value
    abv_be = False
    if avg_for_pos is not None and last_cl is not None and ma_val is not None:
        try:
            abv_be = float(last_cl) > float(avg_for_pos) and float(ma_val) > float(avg_for_pos)
        except Exception:
            abv_be = False

    tf_display = "H" if is_hourly else "D"
    row = SnapshotRow(
        ticker=tk,
        assigned_type=ass.get("type") if ass else None,
        assigned_length=int(ass.get("length")) if ass and ass.get("length") else None,
        assigned_timeframe=tf_display,
        ma_value=ma_value,
        last_close=last_close,
        distance_pct=distance_pct,
        position=ctx.pos_size_map.get(tk, 0.0),
        avg_cost=avg_for_pos,
        abv_be=bool(abv_be),
        ts=ctx.start_ts,
        last_bar_date=last_bar_date,
        assigned_ma=f"{ass.get('type') or ''}({ass.get('length') or ''})" if ass else None,
    )
    return row


def _load_bars_for_ticker(ctx: SnapshotContext, tk: str, key: str, is_hourly: bool) -> List[Dict[str, Any]]:
    if is_hourly:
        return load_bars(key, limit=365)
    new_bars = ctx.daily_results.get(tk, [])
    if new_bars:
        try:
            merge_bars(key, new_bars)
        except Exception:
            append_trace({"event": "merge_failed", "token": tk})
    return load_bars(key, limit=365)


def _extract_closes(bars: List[Dict[str, Any]]) -> List[float]:
    closes: List[float] = []
    for b in bars:
        try:
            c = b.get("Close")
            closes.append(float(c) if c is not None else 0.0)
        except Exception:
            closes.append(0.0)
    return closes


def _compute_last_close_and_bar(bars: List[Dict[str, Any]], snap_dt: Optional[datetime], is_hourly: bool) -> tuple:
    last_close = None
    last_bar_date = None
    chosen = None

    if not bars:
        return None, None, None

    candidates = []
    last_bar = None
    for b in bars:
        bd = b.get("Date")
        if not bd:
            continue
        try:
            bdt = datetime.fromisoformat(str(bd))
        except Exception:
            bdt = None
        if bdt is None:
            continue
        last_bar = b
        if snap_dt is not None and bdt <= snap_dt:
            candidates.append((bdt, b))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        chosen = candidates[-1][1]
    else:
        chosen = last_bar if last_bar is not None else bars[-1]

    if chosen:
        if not is_hourly and snap_dt is not None:
            try:
                bar_date_str = str(chosen.get("Date"))
                bar_date = datetime.fromisoformat(bar_date_str).date()
                snap_date = snap_dt.date()
                if bar_date == snap_date:
                    before_open = (snap_dt.hour < 9) or (snap_dt.hour == 9 and snap_dt.minute < 30)
                    if before_open:
                        prev_daily = [b for b in bars if str(b.get("Date")) != bar_date_str]
                        if prev_daily:
                            chosen = prev_daily[-1]
            except Exception:
                pass

        try:
            last_close = float(chosen.get("Close")) if chosen.get("Close") is not None else None
        except Exception:
            last_close = None
        last_bar_date = chosen.get("Date")

    return last_close, last_bar_date, chosen


def _compute_ma_and_distance(ass: Optional[Dict[str, Any]], closes: List[float], last_close: Optional[float]) -> tuple:
    ma_value = None
    distance_pct = None

    if not ass or not closes:
        return None, None

    try:
        ttype = (ass.get("type") or "").strip().upper()
        l = int(ass.get("length") or 0)
    except Exception:
        ttype = ""
        l = 0

    if not ttype or l <= 0:
        return None, None

    try:
        closes_last = closes[-l:] if len(closes) >= l else closes
        if not closes_last:
            return None, None
        if ttype == "SMA":
            sma_map = compute_sma_series_all(closes_last, [l])
            series = sma_map.get(l, [])
            ma_value = series[-1] if series else None
        else:
            ema_map = compute_ema_series_all(closes_last, [l])
            series = ema_map.get(l, [])
            ma_value = series[-1] if series else None

        if ma_value is not None and last_close is not None:
            try:
                distance_pct = ((last_close - ma_value) / ma_value) * 100.0 if ma_value != 0 else None
            except Exception:
                distance_pct = None
    except Exception:
        pass

    return ma_value, distance_pct


# ---------------------------------------------------------------------------
# Phase 4: Write log
# ---------------------------------------------------------------------------

def _write_snapshot_log(end_ts: str, rows: List[SnapshotRow]) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"start_ts": rows[0].ts if rows else end_ts, "end_ts": end_ts, "rows": [r.to_dict() for r in rows]}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_minute_snapshot(ib_client, tickers: List[str], concurrency: int = 32) -> tuple:
    """Run a minute snapshot cycle.

    Orchestration:
    1. Build context (live positions, open orders, position maps)
    2. Fetch and cache bars for all tickers (daily + hourly)
    3. Handle stale bars (backfill if needed)
    4. Compute per-ticker snapshot rows (MA values, abv_be)
    5. Write results to logs/minute_snapshot.jsonl

    Returns (end_ts: str, rows: List[SnapshotRow]).
    """
    snap_start = time.perf_counter()

    ctx = _build_context(ib_client, tickers)
    _fetch_and_cache(ctx, concurrency=concurrency)

    rows = _compute_snapshot_rows(ctx)

    end_ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()

    _write_snapshot_log(end_ts, rows)

    elapsed = time.perf_counter() - snap_start
    append_trace({"event": "minute_snapshot_done", "tickers": tickers, "count": len(rows), "end_ts": end_ts, "elapsed_ms": elapsed * 1000.0})

    # Return dicts for backward compatibility with existing callers
    return end_ts, [r.to_dict() for r in rows]
