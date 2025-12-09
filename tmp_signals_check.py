import json
from pathlib import Path
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

p = Path('logs/signals.jsonl')
lines = [ln.strip() for ln in p.read_text().splitlines() if ln.strip()]

target_tks = {'NASDAQ:SERV','NASDAQ:RR','NYSE:CRCL','NYSE:PL','NASDAQ:ONDS'}
out_rows = []
for ln in lines[-800:]:
    try:
        j = json.loads(ln)
    except Exception:
        continue
    tk = (j.get('ticker') or j.get('symbol') or '').strip()
    if tk not in target_tks:
        continue
    ts_raw = j.get('ts') or j.get('time') or ''
    try:
        dt = datetime.fromisoformat(ts_raw)
    except Exception:
        continue
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('America/New_York'))
    dt_ny = dt.astimezone(ZoneInfo('America/New_York'))
    # truncate to bucket
    if dt_ny.hour == 9 and dt_ny.minute >= 30:
        bucket = dt_ny.replace(minute=30, second=0, microsecond=0)
    else:
        bucket = dt_ny.replace(minute=0, second=0, microsecond=0)
    out_rows.append({
        "ticker": tk,
        "raw_ts": ts_raw,
        "dt_ny": dt_ny.isoformat(),
        "bucket": bucket.isoformat(),
        "decision": j.get("decision")
    })

for r in out_rows:
    print(json.dumps(r, ensure_ascii=False))


