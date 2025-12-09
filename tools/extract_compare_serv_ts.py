#!/usr/bin/env python3
\"\"\"Timestamped extractor: same behavior as `tools/extract_compare_serv.py` but writes a
timestamped JSONL output to avoid overwriting original files.
\"\"\"
from __future__ import annotations
import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any
import time
import math

# Constants from docs/symbols_db_developer.md
TicksPerMinute = 600_000_000
TicksPerThreeMinutes = 1_800_000_000
TicksPerHalfHour = 18_000_000_000
UnixEpochTicks = 621355968000000000

NY = ZoneInfo("America/New_York")


def stored_to_utc_datetime(stored_int: int, ticks_per_unit: int) -> datetime:
    ticks = int(stored_int) * int(ticks_per_unit)
    unix_seconds = (ticks - UnixEpochTicks) / 10_000_000
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)


def truncate_to_hour_ny(dt_ny: datetime) -> datetime:
    \"\"\"Truncate a NY-local datetime into the project's hour bucket:
    - 09:30..09:59 -> 09:30
    - other times -> HH:00
    Returned dt preserves tzinfo (NY).
    \"\"\"
    if dt_ny.tzinfo is None:
        dt_ny = dt_ny.replace(tzinfo=NY)
    if dt_ny.hour == 9 and dt_ny.minute >= 30:
        return dt_ny.replace(minute=30, second=0, microsecond=0)
    return dt_ny.replace(minute=0, second=0, microsecond=0)


def load_signals(signals_path: Path, symbol: str) -> Dict[datetime, Dict[str, Any]]:
    \"\"\"Load signals.jsonl into a mapping of truncated NY-hour -> original JSON object
    Only keep entries matching the requested symbol (accepts 'SERV' or 'NASDAQ:SERV').
    \"\"\"
    idx: Dict[datetime, Dict[str, Any]] = {}
    if not signals_path.exists():
        print(f\"signals file not found: {signals_path}\")
        return idx
    with signals_path.open(\"r\", encoding=\"utf-8\") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                j = json.loads(ln)
            except Exception:
                continue
            tck = (j.get(\"ticker\") or j.get(\"symbol\") or \"\").strip()
            if not tck:
                continue
            # Accept both plain symbol and EXCHANGE:SYMBOL forms
            if tck.upper() != symbol.upper() and not tck.upper().endswith(f\":{symbol.upper()}\"):
                continue
            ts_raw = j.get(\"ts\") or j.get(\"time\") or j.get(\"timestamp\") or j.get(\"date\") or j.get(\"Date\") or None
            if not ts_raw:
                continue
            try:
                dt = datetime.fromisoformat(ts_raw)
            except Exception:
                # try rough fallback
                try:
                    dt = datetime.fromisoformat(ts_raw.replace(\"Z\", \"+00:00\"))
                except Exception:
                    continue
            # interpret naive timestamps as NY
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=NY)
            dt_ny = dt.astimezone(NY)
            dt_hour_ny = truncate_to_hour_ny(dt_ny)
            idx[dt_hour_ny] = j
    return idx


def aggregate_halfhours_to_hours(rows):
    \"\"\"Aggregate half-hour rows into NY-aligned hour buckets.
    Each row is a tuple (Time, Open, High, Low, Close, Volume).
    Returns mapping dt_hour_utc -> aggregated_row dict.
    \"\"\""
    buckets = defaultdict(list)
    for time_int, open_v, high_v, low_v, close_v, vol in rows:
        dt_utc = stored_to_utc_datetime(time_int, TicksPerHalfHour)
        dt_ny = dt_utc.astimezone(NY)
        hour_ny = truncate_to_hour_ny(dt_ny)
        # normalize key to UTC for lookup
        key_utc = hour_ny.astimezone(timezone.utc)
        buckets[key_utc].append((dt_utc, open_v, high_v, low_v, close_v, vol))

    out = {}
    for key, items in buckets.items():
        # sort by original dt_utc to pick first/last
        items_sorted = sorted(items, key=lambda x: x[0])
        open_v = items_sorted[0][1]
        close_v = items_sorted[-1][4]
        high_v = max(i[2] for i in items_sorted)
        low_v = min(i[3] for i in items_sorted)
        vol = sum(int(i[5]) for i in items_sorted)
        out[key] = {"Open": open_v, "High": high_v, "Low": low_v, "Close": close_v, "Volume": vol}
    return out


def aggregate_minutes_to_hours(rows):
    \"\"\"Aggregate minute rows similarly to halfhours, grouping by NY-hour buckets.\"\"\""
    buckets = defaultdict(list)
    for time_int, open_v, high_v, low_v, close_v, vol in rows:
        dt_utc = stored_to_utc_datetime(time_int, TicksPerMinute)
        dt_ny = dt_utc.astimezone(NY)
        hour_ny = truncate_to_hour_ny(dt_ny)
        key_utc = hour_ny.astimezone(timezone.utc)
        buckets[key_utc].append((dt_utc, open_v, high_v, low_v, close_v, vol))
    out = {}
    for key, items in buckets.items():
        items_sorted = sorted(items, key=lambda x: x[0])
        open_v = items_sorted[0][1]
        close_v = items_sorted[-1][4]
        high_v = max(i[2] for i in items_sorted)
        low_v = min(i[3] for i in items_sorted)
        vol = sum(int(i[5]) for i in items_sorted)
        out[key] = {"Open": open_v, "High": high_v, "Low": low_v, "Close": close_v, "Volume": vol}
    return out


def inspect_symbol_db(symbol_file: Path):
    if not symbol_file.exists():
        raise SystemExit(f"symbol DB not found: {symbol_file}")
    uri = f"file:{symbol_file}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()
    # check for HalfHours
    cur.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name IN ('HalfHours','Minutes')""")
    tables = {r[0] for r in cur.fetchall()}
    hours_map = {}
    if 'HalfHours' in tables:
        cur.execute("SELECT Time, Open, High, Low, Close, Volume FROM HalfHours ORDER BY Time ASC")
        rows = cur.fetchall()
        print(f"Loaded {len(rows)} halfhour rows from {symbol_file.name}")
        hours_map = aggregate_halfhours_to_hours(rows)
    elif 'Minutes' in tables:
        cur.execute("SELECT Time, Open, High, Low, Close, Volume FROM Minutes ORDER BY Time ASC")
        rows = cur.fetchall()
        print(f"Loaded {len(rows)} minute rows from {symbol_file.name}")
        hours_map = aggregate_minutes_to_hours(rows)
    else:
        raise SystemExit("No HalfHours or Minutes table present in DB")
    conn.close()
    return hours_map


def find_mismatches(signals_idx, hours_map):
    mismatches = []
    matches = 0
    missing = 0
    for dt_hour_ny, sig in sorted(signals_idx.items()):
        # Normalize key to UTC
        key_utc = dt_hour_ny.astimezone(timezone.utc)
        sig_close = None
        for k in ('close', 'Close', 'last', 'price'):
            if k in sig:
                try:
                    sig_close = float(sig[k])
                    break
                except Exception:
                    continue
        if key_utc in hours_map:
            bar = hours_map[key_utc]
            bar_close = float(bar['Close'])
            if sig_close is None:
                # can't compare
                missing += 1
                continue
            if abs(bar_close - sig_close) > 1e-9:
                mismatches.append((dt_hour_ny.isoformat(), sig_close, bar_close, sig))
            else:
                matches += 1
        else:
            missing += 1
    return matches, mismatches, missing


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols-dir", required=True, help="Symbols root directory (e.g. .../Snappy/Symbols)")
    p.add_argument("--exchange", default="NASDAQ", help="Exchange id (directory name), default NASDAQ")
    p.add_argument("--symbol", default="SERV", help="Symbol to inspect (no exchange prefix)")
    p.add_argument("--signals-file", default="logs/signals.jsonl", help="Path to signals.jsonl to compare against")
    p.add_argument("--days", type=int, default=5, help="Lookback days (not strictly used in this test)" )
    p.add_argument("--out-dir", default="logs", help="Directory to write comparison output (timestamped file)")
    p.add_argument("--out-prefix", default="signals_extract_compare", help="Prefix for output filename")
    args = p.parse_args()

    symbols_root = Path(args.symbols_dir)
    symbol_file = symbols_root / args.exchange / f"{args.symbol}.sqlite3"
    print(f"Inspecting DB: {symbol_file}")
    hours_map = inspect_symbol_db(symbol_file)

    signals_idx = load_signals(Path(args.signals_file), args.symbol)
    if not signals_idx:
        print("No matching signals found for symbol in signals file.")
        return
    matches, mismatches, missing = find_mismatches(signals_idx, hours_map)
    print(f"Matches: {matches}, Mismatches: {len(mismatches)}, MissingBars(or no close): {missing}")
    if mismatches:
        print("Sample mismatches:")
        for ts, sig_c, bar_c, raw in mismatches[:20]:
            print(f"{ts}  signal_close={sig_c}  db_close={bar_c}  raw_signal={raw}")

    # write timestamped output file so original signals files are not overwritten
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_now = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    out_name = f"{args.out_prefix}_{args.symbol}_{ts_now}.jsonl"
    out_path = out_dir / out_name
    written = 0
    with out_path.open("w", encoding="utf-8") as outf:
        for dt_hour_ny, sig in sorted(signals_idx.items()):
            rec = {"ticker": args.symbol, "ts_hour_ny": dt_hour_ny.isoformat()}
            key_utc = dt_hour_ny.astimezone(timezone.utc)
            sig_close = None
            for k in ('close', 'Close', 'last', 'price'):
                if k in sig:
                    try:
                        sig_close = float(sig[k])
                        break
                    except Exception:
                        continue
            rec["signal_close"] = sig_close
            if key_utc in hours_map:
                bar = hours_map[key_utc]
                rec["db_close"] = float(bar["Close"])
                rec["match"] = (sig_close is not None and abs(rec["db_close"] - sig_close) <= 1e-9)
            else:
                rec["db_close"] = None
                rec["match"] = False
                rec["reason"] = "insufficient_data"
            outf.write(json.dumps(rec, ensure_ascii=False) + "\\n")
            written += 1
    print(f"Wrote comparison output: {out_path} ({written} rows)")


if __name__ == "__main__":
    main()


