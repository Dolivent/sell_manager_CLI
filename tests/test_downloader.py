import types
from sellmanagement.downloader import batch_download_daily, backfill_halfhours_sequential


def test_batch_download_daily_simple(monkeypatch):
    calls = {}

    class FakeIB:
        def download_daily(self, token, duration="1 Y"):
            calls[token] = duration
            return [{"Close": 1.0}]

    ib = FakeIB()
    ticks = [f"EX{i}:T{i}" for i in range(10)]
    res = batch_download_daily(ib, ticks, batch_size=4, batch_delay=0.01, duration="1 Y")
    assert isinstance(res, dict)
    assert set(res.keys()) == set(ticks)
    for v in res.values():
        assert isinstance(v, list)


def test_backfill_halfhours_sequential(monkeypatch):
    # simulate empty for short durations then a long response
    calls = []

    def fake_download_halfhours(token, duration="31 D"):
        calls.append(duration)
        if duration in ("2 D", "7 D"):
            return []
        # return a list of 40 bars
        return [{"close": float(i)} for i in range(40)]

    ib = types.SimpleNamespace()
    ib.download_halfhours = fake_download_halfhours
    rows = backfill_halfhours_sequential(ib, "EX:ABC", target_bars=31)
    assert len(rows) == 31
    # ensure we attempted earlier durations first
    assert "2 D" in calls or "7 D" in calls


def test_aggregate_halfhours_to_hours():
    from sellmanagement.aggregation import aggregate_halfhours_to_hours

    # create 4 halfhour bars (oldest-first)
    halfhours = [
        {"Date": "2025-01-01 09:30:00", "Open": 1, "High": 2, "Low": 1, "Close": 1.5, "Volume": 10},
        {"Date": "2025-01-01 10:00:00", "Open": 1.5, "High": 2.5, "Low": 1.4, "Close": 2.0, "Volume": 20},
        {"Date": "2025-01-01 10:30:00", "Open": 2.0, "High": 2.2, "Low": 1.9, "Close": 2.1, "Volume": 5},
        {"Date": "2025-01-01 11:00:00", "Open": 2.1, "High": 2.4, "Low": 2.0, "Close": 2.3, "Volume": 8},
    ]

    hours = aggregate_halfhours_to_hours(halfhours)
    assert isinstance(hours, list)
    # we expect 2 hourly bars
    assert len(hours) == 2
    assert hours[0]["Open"] == 1
    assert hours[0]["Close"] == 2.0


