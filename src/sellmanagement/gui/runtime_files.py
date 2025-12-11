"""Ensure runtime writable directories and initial files exist (first-run setup)."""
from pathlib import Path
import json

DEFAULT_ASSIGNED_CSV_HEADER = "ticker,type,length,timeframe\n"

def ensure_runtime_files(root: Path | None = None):
    """
    Create runtime folders and files if missing.
    By default uses the current working directory as the application data root.
    """
    if root is None:
        root = Path.cwd()
    config_dir = root / "config"
    logs_dir = root / "logs"
    cache_dir = config_dir / "cache"

    config_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # assigned_ma.csv: create with header if missing
    assigned_path = config_dir / "assigned_ma.csv"
    if not assigned_path.exists():
        with assigned_path.open("w", encoding="utf-8", newline="") as f:
            f.write(DEFAULT_ASSIGNED_CSV_HEADER)

    # signals.jsonl: ensure exists (empty)
    signals_path = logs_dir / "signals.jsonl"
    if not signals_path.exists():
        signals_path.touch()

    # minute_snapshot.jsonl: create an empty placeholder
    minute_path = logs_dir / "minute_snapshot.jsonl"
    if not minute_path.exists():
        # write an initial empty snapshot array entry to avoid parse errors in some readers
        with minute_path.open("w", encoding="utf-8") as f:
            f.write("")  # leave empty; readers handle missing content

    return {
        "config_dir": config_dir,
        "logs_dir": logs_dir,
        "cache_dir": cache_dir,
        "assigned_path": assigned_path,
        "signals_path": signals_path,
        "minute_path": minute_path,
    }













