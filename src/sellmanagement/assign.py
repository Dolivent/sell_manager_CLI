from pathlib import Path
import csv
from typing import Literal, Iterable

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
ASSIGNED_CSV = CONFIG_DIR / "assigned_ma.csv"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def set_assignment(ticker: str, ma_type: str, length: int, timeframe: str = "1H") -> None:
    """Append or update an assignment in config/assigned_ma.csv.

    Ensures header exists and updates existing ticker rows in-place.
    """
    _ensure_config_dir()
    ma_type_up = ma_type.strip().upper()
    if ma_type_up not in ("SMA", "EMA"):
        raise ValueError("type must be SMA or EMA")
    if length <= 0:
        raise ValueError("length must be positive integer")
    timeframe = (timeframe or "1H").strip()
    if timeframe not in ("1H", "D"):
        # accept simple aliases
        tf = timeframe.upper()
        if tf in ("H", "HOURLY"):
            timeframe = "1H"
        elif tf in ("DAY", "DAILY", "D"):
            timeframe = "D"
        else:
            raise ValueError("timeframe must be '1H' or 'D'")

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
        rows.append({"ticker": key, "type": ma_type_up, "length": str(length), "timeframe": timeframe})

    # write back
    # ensure timeframe column exists
    with ASSIGNED_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "type", "length", "timeframe"])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "ticker": r.get("ticker", ""),
                "type": r.get("type", ""),
                "length": r.get("length", ""),
                "timeframe": r.get("timeframe", "1H"),
            })


def get_assignments() -> dict:
    """Read assignments from CSV and return mapping ticker_upper -> {type, length}.

    Returns empty dict when file missing.
    """
    _ensure_config_dir()
    out: dict = {}
    if not ASSIGNED_CSV.exists():
        return out
    with ASSIGNED_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            t = (r.get("ticker") or "").strip()
            if not t:
                continue
            out[t.upper()] = {
                "type": (r.get("type") or "").strip().upper(),
                "length": int((r.get("length") or "0").strip() or 0),
                "timeframe": (r.get("timeframe") or "1H").strip(),
            }
    return out


def get_assignments_list() -> list:
    """Return list of assignment rows in file order.

    Each row is a dict with keys: ticker, type, length, timeframe.
    """
    _ensure_config_dir()
    out: list = []
    if not ASSIGNED_CSV.exists():
        return out
    with ASSIGNED_CSV.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            t = (r.get("ticker") or "").strip()
            if not t:
                continue
            try:
                length = int((r.get("length") or "0").strip() or 0)
            except Exception:
                length = 0
            out.append({
                "ticker": t,
                "type": (r.get("type") or "").strip().upper(),
                "length": length,
                "timeframe": (r.get("timeframe") or "1H").strip(),
            })
    return out


def sync_assignments(tokens: Iterable[str], default_type: str = "SMA", default_length: int = 50, default_timeframe: str = "1H") -> dict:
    """Synchronize `assigned_ma.csv` to exactly the provided `tokens` list.

    - Keeps existing assignments for tokens that are present.
    - Removes assignments for tokens not present anymore.
    - Appends new tokens with defaults.

    Returns a summary dict: {"added": [...], "removed": [...], "kept": [...]}.
    """
    _ensure_config_dir()
    # normalize input tokens
    toks = [t.strip() for t in tokens if t and t.strip()]
    toks_upper = [t.upper() for t in toks]

    existing = get_assignments()  # keyed by upper ticker

    kept = []
    added = []
    rows = []
    for t, t_up in zip(toks, toks_upper):
        if t_up in existing:
            a = existing[t_up]
            rows.append({"ticker": t, "type": a.get("type", "SMA"), "length": str(int(a.get("length") or 0)), "timeframe": a.get("timeframe", default_timeframe)})
            kept.append(t)
        else:
            rows.append({"ticker": t, "type": default_type, "length": str(default_length), "timeframe": default_timeframe})
            added.append(t)

    removed = []
    for k in existing.keys():
        if k not in toks_upper:
            removed.append(k)

    # write out canonical file
    with ASSIGNED_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "type", "length", "timeframe"])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "ticker": r.get("ticker", ""),
                "type": r.get("type", ""),
                "length": r.get("length", ""),
                "timeframe": r.get("timeframe", default_timeframe),
            })

    return {"added": added, "removed": removed, "kept": kept}


