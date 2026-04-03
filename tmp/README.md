# Temporary Working Scripts

> **Purpose:** This folder is for transient, working scripts used during active development or one-off tasks. Scripts here are **not** tracked in version control (see `.gitignore`).

---

## Guidelines

| Rule | Reason |
|------|--------|
| Keep scripts short and focused | Single-purpose scripts are easier to understand and discard |
| Document what the script does | Add a docstring or `--help` output |
| Clean up after use | Delete the script when the task is done |
| No secrets or credentials | Never store passwords, API keys, or account credentials here |
| Prefer the `scripts/` folder for persistent scripts | Scripts that are part of the project belong in `scripts/`, not here |

---

## Current Scripts

| File | Purpose | Created |
|------|---------|---------|
| — | No temporary scripts currently in this folder | — |

---

## Examples

### One-off data inspection

```python
#!/usr/bin/env python3
"""Inspect the signals log for a specific ticker."""
import json
from pathlib import Path

ticker = "NASDAQ:AAPL"
path = Path("logs/signals.jsonl")
with path.open() as f:
    for line in f:
        entry = json.loads(line)
        if entry.get("ticker") == ticker:
            print(entry)
```

### Quick cache inspection

```python
#!/usr/bin/env python3
"""Count cached bars for each ticker."""
from pathlib import Path
import json

cache = Path("config/cache")
for ndjson in cache.glob("*.ndjson"):
    count = sum(1 for _ in ndjson.open())
    print(f"{ndjson.stem}: {count} bars")
```
