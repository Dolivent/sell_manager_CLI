"""Hourly evaluator and structured signal logging.

This module exposes a small API to decide when a close signal is generated
given a list of closes and an assigned MA (type+length). It also provides
helpers to append a JSONL audit log for each decision.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

from .indicators import simple_moving_average, exponential_moving_average
from .config import Config


def _log_path() -> Path:
    # use config dir under sell_manager_CLI/config by default
    base = Path(__file__).resolve().parents[2] / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base / "signals.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def decide(close: float, ma_type: str, length: int, values: List[float]) -> Dict[str, Any]:
    """Return decision dict describing whether to Sell or NoSignal and the MA value."""
    fam = (ma_type or "SMA").strip().upper()
    ma_val: Optional[float]
    if fam == "EMA":
        ma_val = exponential_moving_average(values, length)
    else:
        ma_val = simple_moving_average(values, length)

    if ma_val is None:
        return {"decision": "Skip", "reason": "insufficient_data", "ma_value": None, "close": close}

    if float(close) < float(ma_val):
        return {"decision": "SellSignal", "ma_value": float(ma_val), "close": float(close)}
    else:
        return {"decision": "NoSignal", "ma_value": float(ma_val), "close": float(close)}


def append_signal(entry: Dict[str, Any]) -> bool:
    p = _log_path()
    data = dict(entry)
    data.setdefault("ts", now_iso())
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        # Print a concise terminal message for visibility when signals are generated
        try:
            ticker = data.get("ticker") or data.get("symbol") or "<unknown>"
            decision = data.get("decision") or "<undecided>"
            print(f"signal: {ticker} -> {decision}")
        except Exception:
            # avoid breaking logging on print errors
            pass
        return True
    except Exception:
        return False


