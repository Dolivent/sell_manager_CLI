import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import sellmanagement.assign as assign_mod


class TestMaPresets(unittest.TestCase):
    def test_export_import_roundtrip_replace(self):
        with TemporaryDirectory() as td:
            csv_p = Path(td) / "assigned_ma.csv"
            json_p = Path(td) / "preset.json"
            csv_p.write_text(
                "ticker,type,length,timeframe\nNASDAQ:AA,SMA,10,1H\n",
                encoding="utf-8",
            )
            with patch.object(assign_mod, "ASSIGNED_CSV", csv_p):
                assign_mod.export_assignments_json(json_p)
                self.assertTrue(json_p.exists())
                data = json.loads(json_p.read_text(encoding="utf-8"))
                self.assertEqual(data.get("version"), 1)
                self.assertEqual(len(data.get("assignments", [])), 1)

                csv_p.write_text("ticker,type,length,timeframe\n", encoding="utf-8")
                assign_mod.import_assignments_json(json_p, merge=False)
                rows = assign_mod.get_assignments_list()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["ticker"], "NASDAQ:AA")

    def test_import_merge_upserts(self):
        with TemporaryDirectory() as td:
            csv_p = Path(td) / "assigned_ma.csv"
            json_p = Path(td) / "add.json"
            csv_p.write_text(
                "ticker,type,length,timeframe\nNYSE:BB,SMA,5,D\n",
                encoding="utf-8",
            )
            json_p.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "assignments": [
                            {"ticker": "NYSE:BB", "type": "EMA", "length": 20, "timeframe": "1H"},
                            {"ticker": "NASDAQ:ZZ", "type": "SMA", "length": 50, "timeframe": "D"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(assign_mod, "ASSIGNED_CSV", csv_p):
                assign_mod.import_assignments_json(json_p, merge=True)
                rows = assign_mod.get_assignments_list()
                tickers = {r["ticker"] for r in rows}
                self.assertEqual(tickers, {"NYSE:BB", "NASDAQ:ZZ"})
                by_t = {r["ticker"]: r for r in rows}
                self.assertEqual(by_t["NYSE:BB"]["type"], "EMA")


if __name__ == "__main__":
    unittest.main()
