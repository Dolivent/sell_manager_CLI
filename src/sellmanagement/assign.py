from pathlib import Path
import csv
from typing import Literal

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
ASSIGNED_CSV = CONFIG_DIR / "assigned_ma.csv"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def set_assignment(ticker: str, ma_type: str, length: int) -> None:
    """Append or update an assignment in config/assigned_ma.csv.

    Ensures header exists and updates existing ticker rows in-place.
    """
    _ensure_config_dir()
    ma_type_up = ma_type.strip().upper()
    if ma_type_up not in ("SMA", "EMA"):
        raise ValueError("type must be SMA or EMA")
    if length <= 0:
        raise ValueError("length must be positive integer")

    rows = []
    if ASSIGNED_CSV.exists():
        with ASSIGNED_CSV.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({k: (v or "").strip() for k, v in r.items()})

    updated = False
    key = ticker.strip()
    for r in rows:
        if r.get("ticker", "").strip().upper() == key.upper():
            r["ticker"] = key
            r["type"] = ma_type_up
            r["length"] = str(length)
            updated = True
            break

    if not updated:
        rows.append({"ticker": key, "type": ma_type_up, "length": str(length)})

    # write back
    with ASSIGNED_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "type", "length"])
        writer.writeheader()
        for r in rows:
            writer.writerow({"ticker": r.get("ticker", ""), "type": r.get("type", ""), "length": r.get("length", "")})


