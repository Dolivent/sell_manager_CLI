"""Simple disk cache for historical bars.

This cache stores raw bars as newline-delimited JSON files under
`config/cache/` using the key `EXCHANGE:TICKER:granularity` converted to
filesystem-safe names. The implementation is intentionally small and
easy to replace with parquet/SQLite later.
"""
from pathlib import Path
import json
from typing import Iterable, Any, List


CACHE_DIR = Path(__file__).resolve().parents[2] / "config" / "cache"


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key_to_path(key: str) -> Path:
    # key expected: EXCHANGE:TICKER:granularity
    safe = key.replace(':', '__').replace('/', '_')
    return CACHE_DIR / f"{safe}.ndjson"


def _default_serializer(o):
    # common non-serializable types
    try:
        import datetime

        if isinstance(o, datetime.datetime):
            return o.isoformat()
    except Exception:
        pass
    try:
        return str(o)
    except Exception:
        return None


def persist_bars(key: str, bars: Iterable[dict]) -> None:
    """Append bars (iterable of dict) to the cache file for `key`.

    This is append-only to make writes crash-safe in simple cases.
    """
    _ensure_cache_dir()
    p = _key_to_path(key)
    with p.open("a", encoding="utf-8") as f:
        for b in bars:
            try:
                f.write(json.dumps(b, ensure_ascii=False, default=_default_serializer) + "\n")
            except Exception:
                try:
                    f.write(json.dumps(str(b), ensure_ascii=False) + "\n")
                except Exception:
                    # drop problematic item
                    continue


def load_bars(key: str, limit: int | None = None) -> List[Any]:
    """Load bars for `key`. Returns list of dicts (newest last).

    If `limit` is set, returns up to the last `limit` rows.
    """
    p = _key_to_path(key)
    if not p.exists():
        return []
    out: List[Any] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # skip malformed lines
                continue
    if limit is None or limit <= 0:
        return out
    return out[-limit:]


def write_bars(key: str, bars: Iterable[dict]) -> None:
    """Overwrite the cache file for `key` with the provided bars.

    This writes all items in `bars` (iterable of dict) to the file, replacing
    any existing content. Use with care.
    """
    _ensure_cache_dir()
    p = _key_to_path(key)
    with p.open("w", encoding="utf-8") as f:
        for b in bars:
            try:
                f.write(json.dumps(b, ensure_ascii=False, default=_default_serializer) + "\n")
            except Exception:
                try:
                    f.write(json.dumps(str(b), ensure_ascii=False) + "\n")
                except Exception:
                    continue


def merge_bars(key: str, new_bars: Iterable[dict]) -> None:
    """Merge `new_bars` into existing cache for `key`.

    Matching is done by the `Date` field: new items replace existing items with
    the same `Date`. The final file is sorted by `Date` in ascending order (if
    Date values are comparable as strings).
    """
    # load existing
    existing = load_bars(key)
    # build map by Date
    by_date: dict = {}
    for r in existing:
        d = r.get("Date")
        if d is None:
            # use raw string fallback
            continue
        by_date[str(d)] = r

    # incorporate new bars
    for nb in new_bars:
        d = nb.get("Date")
        if d is None:
            # skip items without date
            continue
        by_date[str(d)] = nb

    # sort by date key (as string) and write back
    merged = [by_date[k] for k in sorted(by_date.keys())]
    write_bars(key, merged)


