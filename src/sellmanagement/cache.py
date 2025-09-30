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


def persist_bars(key: str, bars: Iterable[dict]) -> None:
    """Append bars (iterable of dict) to the cache file for `key`.

    This is append-only to make writes crash-safe in simple cases.
    """
    _ensure_cache_dir()
    p = _key_to_path(key)
    with p.open("a", encoding="utf-8") as f:
        for b in bars:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


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


