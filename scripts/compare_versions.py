#!/usr/bin/env python3
"""
Compare MA values and resulting decisions between the backup pre-GUI code tree
and the current workspace. Produces JSON and markdown reports under
docs/@docs/.

This script is intentionally self-contained and uses only stdlib imports so it
can run in CI without additional deps.
"""
from pathlib import Path
import csv
import json
import importlib.util
from typing import Dict, Any, Tuple, List
import math
import os


ROOT = Path(__file__).resolve().parents[1]
BACKUP_SRC = ROOT / "docs" / "sell_manager_CLI - backup pre 20251206" / "src"
CURRENT_SRC = ROOT / "src"
OUT_DIR = Path("docs") / "@docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_assignments_from_csv(csv_path: Path) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not csv_path.exists():
        return out
    with csv_path.open("r", newline="") as fh:
        r = csv.DictReader(fh)
        for row in r:
            t = (row.get("ticker") or "").strip()
            if not t:
                continue
            out[t] = {
                "type": (row.get("type") or "").strip().upper(),
                "length": int((row.get("length") or "0").strip() or 0),
                "timeframe": (row.get("timeframe") or "").strip(),
            }
    return out


def load_module_from_path(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {path}")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore
    return m


def _cache_key_for_timeframe(ticker: str, timeframe: str) -> str:
    tf = (timeframe or "1H").strip().upper()
    if tf in ("1H", "H", "HOURLY"):
        return f"{ticker}:1h"
    return f"{ticker}:1d"


def compute_last_ma(indicators_module, closes: List[float], ma_type: str, length: int) -> Any:
    if not closes or length <= 0:
        return None
    fam = (ma_type or "SMA").strip().upper()
    try:
        if fam == "EMA":
            ema_map = indicators_module.compute_ema_series_all(closes, [length])
            series = ema_map.get(length, [])
            return series[-1] if series else None
        else:
            sma_map = indicators_module.compute_sma_series_all(closes, [length])
            series = sma_map.get(length, [])
            return series[-1] if series else None
    except Exception:
        return None


def compare_and_report(output_dir: Path = OUT_DIR) -> Dict[str, Any]:
    # read assignments from both trees
    backup_csv = Path(BACKUP_SRC).resolve().parents[0] / "config" / "assigned_ma.csv"
    current_csv = Path(CURRENT_SRC).resolve().parents[0] / "config" / "assigned_ma.csv"
    backup_assign = read_assignments_from_csv(backup_csv)
    current_assign = read_assignments_from_csv(current_csv)

    # load current cache loader (shared disk cache)
    cache_path = CURRENT_SRC / "sellmanagement" / "cache.py"
    cache_mod = load_module_from_path(cache_path, "cache_current")

    # load indicators modules from both trees
    ind_backup = load_module_from_path(BACKUP_SRC / "sellmanagement" / "indicators.py", "ind_backup")
    ind_current = load_module_from_path(CURRENT_SRC / "sellmanagement" / "indicators.py", "ind_current")

    tickers = sorted(set(list(backup_assign.keys()) + list(current_assign.keys())))
    results: Dict[str, Any] = {}
    for tk in tickers:
        ba = backup_assign.get(tk)
        ca = current_assign.get(tk)
        # prefer timeframe from current assignment if present, else backup
        tf = (ca or ba or {}).get("timeframe") or "1H"
        key = _cache_key_for_timeframe(tk, tf)
        bars = cache_mod.load_bars(key) if hasattr(cache_mod, "load_bars") else []
        # extract closes (newest-last)
        closes: List[float] = []
        for b in bars:
            try:
                c = b.get("Close")
                closes.append(float(c) if c is not None else 0.0)
            except Exception:
                closes.append(0.0)

        last_close = closes[-1] if closes else None

        backup_ma = None
        current_ma = None
        backup_decision = None
        current_decision = None

        if ba and closes:
            backup_ma = compute_last_ma(ind_backup, closes, ba.get("type", "SMA"), int(ba.get("length") or 0))
            try:
                backup_decision = None if backup_ma is None or last_close is None else (float(last_close) < float(backup_ma))
            except Exception:
                backup_decision = None

        if ca and closes:
            current_ma = compute_last_ma(ind_current, closes, ca.get("type", "SMA"), int(ca.get("length") or 0))
            try:
                current_decision = None if current_ma is None or last_close is None else (float(last_close) < float(current_ma))
            except Exception:
                current_decision = None

        diff = False
        if (backup_ma is None) != (current_ma is None):
            diff = True
        else:
            try:
                if backup_ma is None and current_ma is None:
                    diff = False
                else:
                    # numeric compare with tolerance
                    diff = abs(float(backup_ma) - float(current_ma)) > 1e-9 or backup_decision != current_decision
            except Exception:
                diff = True

        results[tk] = {
            "ticker": tk,
            "backup_assignment": ba,
            "current_assignment": ca,
            "last_close": None if last_close is None else float(last_close),
            "backup_ma": None if backup_ma is None else float(backup_ma),
            "current_ma": None if current_ma is None else float(current_ma),
            "backup_decision_sell": backup_decision,
            "current_decision_sell": current_decision,
            "different": bool(diff),
        }

    # write json and markdown
    json_out = output_dir / "comparison_results.json"
    md_out = output_dir / "comparison_results.md"
    with json_out.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    # create human-readable report
    lines: List[str] = []
    lines.append("# Comparison results: backup vs current\n")
    for tk, r in sorted(results.items()):
        lines.append(f"- **{tk}**: different={r['different']}")
        lines.append(f"  - last_close: {r['last_close']}")
        lines.append(f"  - backup assignment: {r['backup_assignment']}")
        lines.append(f"  - current assignment: {r['current_assignment']}")
        lines.append(f"  - backup_ma: {r['backup_ma']}")
        lines.append(f"  - current_ma: {r['current_ma']}")
        lines.append(f"  - backup_sell?: {r['backup_decision_sell']}")
        lines.append(f"  - current_sell?: {r['current_decision_sell']}")
        lines.append("")

    with md_out.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return results


def main():
    res = compare_and_report()
    diffs = [k for k, v in res.items() if v.get("different")]
    print(f"Compared {len(res)} tickers; differences: {len(diffs)}")
    if diffs:
        for d in diffs:
            print("  -", d)


if __name__ == "__main__":
    main()


