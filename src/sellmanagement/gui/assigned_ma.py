"""Utilities to read/write config/assigned_ma.csv."""
from pathlib import Path
import csv
from typing import Dict, Iterator


class AssignedMAStore:
    def __init__(self, path: Path | None = None):
        # Resolve config directory robustly by walking up ancestors looking for a 'config' folder.
        if path:
            self.path = Path(path)
            return

        p = Path(__file__).resolve()
        config_dir = None
        # check up to 6 levels up for a 'config' directory
        for i in range(1, 7):
            candidate = p.parents[i] / "config"
            if candidate.exists() and candidate.is_dir():
                config_dir = candidate
                break
        if config_dir is None:
            # fallback to repository root 'config' (one level above src) or cwd/config
            alt = Path(__file__).resolve().parents[3] / "config"
            if alt.exists() and alt.is_dir():
                config_dir = alt
            else:
                config_dir = Path.cwd() / "config"

        self.path = config_dir / "assigned_ma.csv"

    def iter_rows(self) -> Iterator[Dict[str, str]]:
        if not self.path.exists():
            return iter([])
        with self.path.open("r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                # normalize keys to lowercase
                yield {k.strip(): v.strip() for k, v in row.items()}

    def write_rows(self, rows):
        # atomic write: write to temp then replace
        tmp = self.path.with_suffix(".tmp")
        fieldnames = ["ticker", "type", "length", "timeframe"]
        with tmp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fieldnames})
        tmp.replace(self.path)


