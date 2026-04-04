import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sellmanagement.dashboard import (
    create_app,
    dashboard_port,
    read_latest_snapshot_record,
)


class TestDashboard(unittest.TestCase):
    def test_read_latest_snapshot_record(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "m.jsonl"
            p.write_text(
                json.dumps({"ts": "t0", "rows": []}) + "\n"
                + json.dumps({"ts": "t1", "rows": [{"ticker": "X"}]}) + "\n",
                encoding="utf-8",
            )
            rec = read_latest_snapshot_record(p)
            self.assertIsNotNone(rec)
            assert rec is not None
            self.assertEqual(rec["ts"], "t1")

    def test_index_renders_rows(self):
        with TemporaryDirectory() as td:
            snap = Path(td) / "minute_snapshot.jsonl"
            sig = Path(td) / "signals.jsonl"
            snap.write_text(
                json.dumps(
                    {
                        "ts": "2026-01-01T12:00:00",
                        "rows": [
                            {
                                "ticker": "NASDAQ:ZZZ",
                                "last_close": 10,
                                "ma_value": 11,
                                "distance_pct": -1,
                                "assigned_ma": "SMA 50",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            sig.write_text(
                json.dumps(
                    {
                        "ts": "2026-01-01T12:00:05",
                        "ticker": "NASDAQ:ZZZ",
                        "decision": "SellSignal",
                        "close": 10,
                        "ma_value": 11,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            app = create_app(snapshot_path=snap, signals_path=sig)
            c = app.test_client()
            rv = c.get("/")
            self.assertEqual(rv.status_code, 200)
            self.assertIn(b"NASDAQ:ZZZ", rv.data)
            self.assertIn(b"SellSignal", rv.data)

    def test_dashboard_port_from_env(self):
        with patch.dict(os.environ, {"SELLMANAGEMENT_DASHBOARD_PORT": "6001"}, clear=False):
            self.assertEqual(dashboard_port(), 6001)


if __name__ == "__main__":
    unittest.main()
