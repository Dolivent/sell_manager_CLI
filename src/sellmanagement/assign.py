from pathlib import Path
import csv
import json
from typing import Any, Dict, Iterable, List, Union

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
    # allow empty timeframe to represent "not assigned"; otherwise normalize
    timeframe = (timeframe or "").strip()
    if timeframe:
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
            r["timeframe"] = timeframe
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
            "timeframe": (r.get("timeframe") or "").strip(),
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
            "timeframe": (r.get("timeframe") or "").strip(),
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


def sync_assignments_to_positions(tokens: Iterable[str]) -> dict:
    """Synchronize `assigned_ma.csv` to exactly the provided `tokens` list using existing assignments.

    - Keeps existing assignments for tokens that are present.
    - Removes assignments for tokens not present anymore.
    - Appends new tokens but leaves their assignment fields blank (for interactive assignment later).

    Returns a summary dict: {"added": [...], "removed": [...], "kept": [...]}.
    """
    _ensure_config_dir()
    toks = [t.strip() for t in tokens if t and t.strip()]
    toks_upper = [t.upper() for t in toks]

    existing = get_assignments()  # keyed by upper ticker

    kept = []
    added = []
    rows = []
    for t, t_up in zip(toks, toks_upper):
        if t_up in existing:
            a = existing[t_up]
            rows.append({
                "ticker": t,
                "type": a.get("type", ""),
                "length": str(int(a.get("length") or 0)) if a.get("length") else "",
                "timeframe": a.get("timeframe", ""),
            })
            kept.append(t)
        else:
            # Try symbol-only fallback: if existing has an entry for the symbol without exchange, reuse it.
            sym_only = t_up.split(":")[-1]
            found = None
            for ex_key, ex_val in existing.items():
                if ex_key.split(":")[-1] == sym_only:
                    found = ex_val
                    break
            if found:
                rows.append({
                    "ticker": t,
                    "type": found.get("type", ""),
                    "length": str(int(found.get("length") or 0)) if found.get("length") else "",
                    "timeframe": found.get("timeframe", ""),
                })
                kept.append(t)
            else:
                # new token: leave assignment blank for interactive flow
                rows.append({"ticker": t, "type": "", "length": "", "timeframe": ""})
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
                "timeframe": r.get("timeframe", ""),
            })

    return {"added": added, "removed": removed, "kept": kept}


_PRESET_VERSION = 1


def _coerce_timeframe(timeframe: str) -> str:
    """Normalize timeframe string; raises ValueError if invalid."""
    timeframe = (timeframe or "").strip()
    if not timeframe:
        return "1H"
    if timeframe in ("1H", "D"):
        return timeframe
    tf = timeframe.upper()
    if tf in ("H", "HOURLY"):
        return "1H"
    if tf in ("DAY", "DAILY", "D"):
        return "D"
    raise ValueError("timeframe must be '1H' or 'D'")


def _parse_preset_row(obj: object) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("assignment must be a JSON object")
    ticker = str(obj.get("ticker") or "").strip()
    if not ticker:
        raise ValueError("missing ticker")
    typ = str(obj.get("type") or "").strip().upper()
    if typ not in ("SMA", "EMA"):
        raise ValueError("type must be SMA or EMA")
    try:
        length = int(obj.get("length"))
    except Exception as e:
        raise ValueError("invalid length") from e
    if length <= 0:
        raise ValueError("length must be positive")
    tf = _coerce_timeframe(str(obj.get("timeframe") or "1H").strip() or "1H")
    return {"ticker": ticker, "type": typ, "length": length, "timeframe": tf}


def _write_csv_rows(rows: List[Dict[str, Any]]) -> None:
    _ensure_config_dir()
    with ASSIGNED_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "type", "length", "timeframe"])
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "ticker": r.get("ticker", ""),
                    "type": r.get("type", ""),
                    "length": str(int(r.get("length", 0))),
                    "timeframe": r.get("timeframe", "1H"),
                }
            )


def export_assignments_json(dest: Union[str, Path]) -> None:
    """Write current assignments to a JSON preset file."""
    rows = get_assignments_list()
    serializable = [
        {
            "ticker": r.get("ticker", ""),
            "type": r.get("type", ""),
            "length": int(r.get("length") or 0),
            "timeframe": (r.get("timeframe") or "1H") or "1H",
        }
        for r in rows
    ]
    payload = {"version": _PRESET_VERSION, "assignments": serializable}
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def import_assignments_json(path: Union[str, Path], *, merge: bool = False) -> Dict[str, Any]:
    """Load assignments from JSON. Replace entire CSV by default, or merge (upsert by ticker)."""
    raw_text = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw_text)
    rows_in = data.get("assignments")
    if rows_in is None and isinstance(data, list):
        rows_in = data
    if not isinstance(rows_in, list):
        raise ValueError("preset must contain an 'assignments' array (or be a bare array)")

    parsed = [_parse_preset_row(x) for x in rows_in]

    if merge:
        for r in parsed:
            set_assignment(
                r["ticker"],
                r["type"],
                int(r["length"]),
                timeframe=r["timeframe"],
            )
        return {"mode": "merge", "count": len(parsed)}

    _write_csv_rows(parsed)
    return {"mode": "replace", "count": len(parsed)}

