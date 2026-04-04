# T005 — Implement Proper Logging Instead of `trace.py`

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T005 |
| Title | Implement proper logging instead of `trace.py` |
| Status | DONE |
| Priority | P2 |
| Created | 2026-04-04 |
| Session completed | S004 |
| Detail File | `docs/03-tasks/tracker/T005-proper-logging.md` |

---

## 1. Goal

Replace the append-only `trace.py` approach with Python's `logging` module using structured log records, configured with appropriate handlers for file + console output and consistent log levels.

---

## 2. Background

Currently `trace.py` uses a custom append-only approach:

```python
def append_trace(record: dict) -> None:
    with open("logs/ibkr_download_trace.log", "a") as f:
        f.write(json.dumps({"ts": ..., **record}) + "\n")
```

Problems with this approach:
- No log levels (DEBUG, INFO, WARNING, ERROR)
- No rotation — log file grows indefinitely
- No console output in CLI mode
- Custom timestamp format (not ISO8601 by default)
- Custom `trace.py` module must be imported everywhere

---

## 3. Design

### Use Python `logging` with Structured Records

```python
import logging
import logging.handlers

def setup_logging(log_dir: Path = Path("logs"), level=logging.INFO):
    # File handler: rotate at 10MB, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10_000_000,
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(
        '{"ts": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "msg": "%(message)s"}'
    ))

    # Console handler (CLI only)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root = logging.getLogger()
    root.addHandler(file_handler)
    root.addHandler(console)
    root.setLevel(level)
```

### Usage in Modules

```python
logger = logging.getLogger(__name__)

def run_minute_snapshot(...):
    logger.info("Starting snapshot for %d tickers", len(tickers))
    logger.debug("IB positions: %s", positions)
    try:
        ...
    except Exception:
        logger.error("Snapshot failed", exc_info=True)
```

---

## 4. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rotation | `RotatingFileHandler` | 10MB / 5 backups — sufficient for minute-by-minute logs |
| Format | JSON per line | Maintains parseability for log analysis tools |
| Level defaults | INFO for file, WARNING for console | Verbose file, quiet console |
| Timestamp | ISO8601 via `asctime` | Consistent with existing audit logs |

---

## 5. Acceptance Criteria

- [x] `trace.py` uses the `logging` module internally (`Logger` + `RotatingFileHandler`)
- [x] Trace log rotates at 10MB with 5 backups (`logs/ibkr_download_trace.log`)
- [ ] Console handler / WARNING-only CLI output (deferred — trace remains file-only)
- [x] All `append_trace` call sites unchanged (same public API and JSONL-compatible lines)
- [ ] `logs/app.log` — not introduced; existing trace path retained for compatibility
- [ ] Unit tests for logging output (deferred)

## 6. Resolution (S004) — phase 1

`append_trace(dict)` is unchanged at call sites. Implementation now builds a dedicated logger `sellmanagement.trace`, writes one JSON object per log line to the same path as before, and uses `RotatingFileHandler`. Further work: optional console mirror, migrate modules to `logging.getLogger(__name__)` with levels, and retire the `append_trace` wrapper where appropriate.
