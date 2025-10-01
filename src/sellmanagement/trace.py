from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json


def _trace_path() -> Path:
    p = Path(__file__).resolve().parents[2] / "logs" / "ibkr_download_trace.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_trace(record: dict) -> None:
    try:
        p = _trace_path()
        # use America/New_York for trace timestamps
        ts = datetime.now(tz=ZoneInfo("America/New_York")).isoformat()
        data = {"ts": ts, **record}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort tracing: ignore failures
        pass


