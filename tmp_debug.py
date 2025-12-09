import json
from pathlib import Path
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
signals_path = Path('logs/signals.jsonl')
print('exists', signals_path.exists())
lines = signals_path.read_text().splitlines()
print('total lines', len(lines))

def truncate_to_hour(dt_ny):
    if dt_ny.hour == 9 and dt_ny.minute >= 30 and dt_ny.minute < 60:
        return dt_ny.replace(minute=30, second=0, microsecond=0)
    return dt_ny.replace(minute=0, second=0, microsecond=0)

raw = {}
tickers = set()
times = {}
for ln in lines[-1000:]:
    try:
        j = json.loads(ln)
    except Exception:
        continue
    ticker = (j.get('ticker') or j.get('symbol') or '').strip()
    ts_raw = j.get('ts') or j.get('time') or ''
    decision = j.get('decision') or ''
    if not ticker or not ts_raw:
        continue
    try:
        dt = datetime.fromisoformat(ts_raw)
    except Exception:
        continue
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('America/New_York'))
    dt_ny = dt.astimezone(ZoneInfo('America/New_York'))
    tpart = dt_ny.time()
    if (tpart < dt_time(9,30)) or (tpart > dt_time(16,0)):
        continue
    dt_hour = truncate_to_hour(dt_ny)
    ts_hour = dt_hour.isoformat()
    tickers.add(ticker)
    times[ts_hour] = dt_hour
    raw.setdefault((ts_hour, ticker), []).append(decision)

def merge(decisions):
    for d in decisions:
        if str(d).strip().lower() == 'sellsignal':
            return 'SellSignal'
    for d in decisions:
        d_str = str(d).strip()
        if d_str and d_str.lower() != 'nosignal':
            return d_str
    return 'NoSignal'

decisions = {}
for (ts_hour, ticker), dec_list in raw.items():
    decisions.setdefault(ts_hour, {})[ticker] = merge(dec_list)

from datetime import datetime as dtcls
dates = set(dt.date() for dt in times.values())
generated = set()
for d in dates:
    hours = [9] + list(range(10,17))
    for hr in hours:
        minute = 30 if hr==9 else 0
        dt_hour = dtcls(d.year,d.month,d.day,hr,minute,0,tzinfo=ZoneInfo('America/New_York')).replace(microsecond=0)
        ts_hour = dt_hour.isoformat()
        if ts_hour not in times:
            times[ts_hour] = dt_hour
            generated.add(ts_hour)

bucket_ts = '2025-12-08T16:00:00-05:00'
print('Bucket', bucket_ts)
print('Generated:', bucket_ts in generated)
print('Decisions:', decisions.get(bucket_ts, {}))

bucket_ts2 = '2025-12-08T15:00:00-05:00'
print('Bucket', bucket_ts2)
print('Generated:', bucket_ts2 in generated)
print('Decisions:', decisions.get(bucket_ts2, {}))

bucket_ts3 = '2025-12-08T09:30:00-05:00'
print('Bucket', bucket_ts3)
print('Generated:', bucket_ts3 in generated)
print('Decisions:', decisions.get(bucket_ts3, {}))
