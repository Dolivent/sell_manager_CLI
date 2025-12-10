from pathlib import Path
import json
from typing import Optional, Dict, Any


def _store_path() -> Path:
    # logs/intents.jsonl at project root
    return Path(__file__).resolve().parents[2] / "logs" / "intents.jsonl"


def _ensure_parent() -> None:
    p = _store_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def write_intent(intent: Dict[str, Any]) -> None:
    """Append an intent record (JSON) to the store."""
    _ensure_parent()
    try:
        with _store_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(intent, default=str) + "\n")
    except Exception:
        # best-effort append; do not raise for caller simplicity
        return


def exists(intent_id: str) -> bool:
    """Return True if an intent with this id already exists in the store."""
    p = _store_path()
    if not p.exists():
        return False
    try:
        with p.open("r", encoding="utf-8") as fh:
            for ln in fh:
                try:
                    j = json.loads(ln)
                except Exception:
                    continue
                if j.get("intent_id") == intent_id:
                    return True
    except Exception:
        return False
    return False


def update_intent(intent_id: str, updates: Dict[str, Any]) -> None:
    """Append an update record for the intent (simple append-only approach)."""
    # Keep append-only semantics to avoid complex in-place editing.
    rec = {"intent_id": intent_id, "update": updates}
    write_intent(rec)


def read_recent(limit: int = 200) -> list[Dict[str, Any]]:
    """Return the last `limit` intent records (naive tail read)."""
    p = _store_path()
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        head = lines[-limit:]
        out = []
        for ln in head:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


