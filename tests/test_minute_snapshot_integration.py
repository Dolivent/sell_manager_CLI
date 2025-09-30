import json
from pathlib import Path

from sellmanagement.minute_snapshot import run_minute_snapshot

import sellmanagement.cache as cache_mod
import sellmanagement.assign as assign_mod


class FakeIB:
    def download_halfhours(self, token: str, duration: str = "31 D", max_bars: int | None = 31, endDateTime: str = ""):
        # return four half-hour bars across two hours (09:00+09:30 -> hour 09, 10:00+10:30 -> hour 10)
        return [
            {"Date": "2025-01-01T09:00:00", "Open": 8, "High": 8, "Low": 8, "Close": 8, "Volume": 1},
            {"Date": "2025-01-01T09:30:00", "Open": 8, "High": 9, "Low": 8, "Close": 9, "Volume": 1},
            {"Date": "2025-01-01T10:00:00", "Open": 10, "High": 10, "Low": 10, "Close": 10, "Volume": 1},
            {"Date": "2025-01-01T10:30:00", "Open": 11, "High": 12, "Low": 11, "Close": 12, "Volume": 1},
        ]


def test_minute_snapshot_integration(tmp_path, monkeypatch):
    # redirect cache dir to tmp
    cache_dir = tmp_path / "config" / "cache"
    monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # assignment: hourly SMA length 2 for token
    assign = [{"ticker": "EX:SYM", "type": "SMA", "length": 2, "timeframe": "1H"}]
    # minute_snapshot imported get_assignments_list at import time; patch it there
    import sellmanagement.minute_snapshot as ms
    monkeypatch.setattr(ms, "get_assignments_list", lambda: assign)

    fake = FakeIB()
    rows = run_minute_snapshot(fake, ["EX:SYM"], concurrency=1)
    assert rows and len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "EX:SYM"
    # aggregated hourly closes should be [9, 12], SMA(2) == 10.5
    assert abs(r["ma_value"] - 10.5) < 1e-9
    assert r["last_close"] == 12.0
    assert r["distance_pct"] is not None

    # log file written
    log_path = Path(__file__).resolve().parents[1] / "logs" / "minute_snapshot.jsonl"
    assert log_path.exists()
    with log_path.open() as f:
        lines = [line for line in f if line.strip()]
    assert lines, "minute_snapshot log should contain at least one entry"
    obj = json.loads(lines[-1])
    assert "rows" in obj


