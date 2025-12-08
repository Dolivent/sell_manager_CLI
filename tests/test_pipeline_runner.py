import pytest
import threading

from src.sellmanagement.gui.pipeline import PipelineRunner


class FakeIBWorker:
    def __init__(self):
        self._client = type('FakeClient', (), {
            'positions': lambda: []
        })()

    def run_on_thread(self, fn, timeout=None):
        # simply execute the callable synchronously for testing
        return fn()


def test_run_snapshot_once(monkeypatch):
    # monkeypatch run_minute_snapshot and get_assignments_list
    from src.sellmanagement.gui.pipeline import PipelineRunner

    called = {}

    def fake_get_assignments_list():
        return [{"ticker": "NASDAQ:TSLA", "type": "SMA", "length": 20, "timeframe": "1H"}]

    def fake_sync_assignments_to_positions(tokens):
        return {"added": [], "removed": [], "kept": tokens}

    def fake_run_minute_snapshot(client, tickers, concurrency=32):
        called['tickers'] = tickers
        return ("2025-12-07T12:00:00-05:00", [{"ticker": "NASDAQ:TSLA", "last_close": 100.0, "ma_value": 110.0, "position": 1.0}])

    # patch the modules where they're imported from
    monkeypatch.setattr("src.sellmanagement.minute_snapshot.run_minute_snapshot", fake_run_minute_snapshot, raising=False)
    monkeypatch.setattr("src.sellmanagement.assign.get_assignments_list", fake_get_assignments_list, raising=False)
    monkeypatch.setattr("src.sellmanagement.assign.sync_assignments_to_positions", fake_sync_assignments_to_positions, raising=False)

    ibw = FakeIBWorker()
    runner = PipelineRunner(ibw)
    end_ts, rows = runner.run_snapshot_once()
    assert end_ts.startswith("2025-12-07")
    assert isinstance(rows, list)
    assert called.get('tickers') == ["NASDAQ:TSLA"]


