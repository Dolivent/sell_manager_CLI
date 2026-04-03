# Database guide (read-only)

This document explains how to inspect and use the project's read-only SQLite databases, how the data is laid out, and important notes about time representations and conversions (especially differences between common C# formats and Python/unix epochs).

- **Location:** `2025 review/database/` (reference copies of original project code are in `2025 review/database/reference/`)
- **Files:** look for `*.sqlite` / `*.sqlite3` files in the data directories you work with; these are intended to be opened read-only.

## Goals
- Show how to open an SQLite DB read-only from CLI and Python.
- Give quick ways to inspect schema and table contents.
- Explain the common tables/fields and their intended meaning.
- Explain time formats used by tooling around the codebase and provide Python conversion examples (C# ticks, Unix seconds/ms).

## Open the DB safely (read-only)
- CLI (read-only):  
  sqlite3 path/to/file.sqlite ".tables"  
  sqlite3 path/to/file.sqlite "PRAGMA schema_version;"  

- From Python (recommended for inspection scripts) — open read-only to avoid accidental writes:

```python
import sqlite3

db_path = r"C:\path\to\data.sqlite"
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall()]
print(tables)
```

- If you need to run write operations (not recommended), copy the DB first:
```bash
cp path/to/file.sqlite /tmp/mycopy.sqlite
# operate on /tmp/mycopy.sqlite
```

## Quick inspection queries
- Show schema for a table:
```sql
PRAGMA table_info('Days');
```

- Show first N rows:
```sql
SELECT * FROM Days ORDER BY day_ts LIMIT 20;
```

- Useful pragmas:
```sql
PRAGMA user_version;     -- schema version set by app
PRAGMA quick_check;      -- integrity
PRAGMA page_size;        -- internal page size
```

## Typical tables and fields (overview)
The exact names and columns may vary by version. Look in the `reference/` copies of the original code (e.g., `Database.cs` / `Download/*` in `reference/`) for authoritative mappings. Typical tables you will see:

- `Symbols` or `SymbolInfo` — metadata for instruments (symbol, exchange, timezone, tick size, etc.)
- `Days` — aggregated daily bars; common columns: symbol, day_ts (time), open, high, low, close, volume
- `Minutes`, `ThreeMinutes`, `HalfHours` — intraday rows at different resolutions; common columns: symbol, ts, open, high, low, close, volume
- `Earnings`, `Dividends` — corporate events

## Mapping a symbol to its DB file
If you have a ticker like `NASDAQ:PLTR` and want the corresponding DB file, the project uses a straightforward directory / filename convention in most installs:

- Typical path pattern (Windows, `%APPDATA%`):
  `%APPDATA%\Snappy\Symbols\<EXCHANGE>\<SYMBOL>.sqlite3`  
  Example: `C:\Users\<user>\AppData\Roaming\Snappy\Symbols\NASDAQ\PLTR.sqlite3`

- Notes on normalization:
  - Input like `NASDAQ:PLTR` should be split on `:` → exchange=`NASDAQ`, symbol=`PLTR`.
  - Filenames are typically the raw symbol (uppercase) with `.sqlite3` (sometimes `.sqlite`). Windows is case-insensitive.
  - Some symbols containing punctuation or special chars may be normalized (e.g., `/` -> `_`) — check the exchange directory if a direct filename is missing.
  - If the app stores a central manifest table (e.g., `Symbols` / `SymbolInfo`) it may include a `filename` or `path` field — prefer querying that if present.

- PowerShell check (build path + test)
  ```powershell
  $ex="NASDAQ"; $sym="PLTR"
  $path = Join-Path $env:APPDATA "Snappy\Symbols\$ex\$sym.sqlite3"
  Test-Path $path
  ```

- Fallback search (if not at expected path)
  ```powershell
  Get-ChildItem -Path (Join-Path $env:APPDATA "Snappy\Symbols") -Filter "*PLTR*.sqlite*" -Recurse
  ```

- Python example (construct path and test)
  ```python
  from pathlib import Path
  import os

  exchange, symbol = "NASDAQ", "PLTR"
  p = Path(os.environ['APPDATA']) / "Snappy" / "Symbols" / exchange / f"{symbol}.sqlite3"
  print(p, p.exists())
  ```

- Inspect the `Symbols` table if present:
  ```sql
  PRAGMA table_info('Symbols');
  SELECT * FROM Symbols WHERE symbol = 'PLTR' LIMIT 5;
  ```
  If the table contains a `filename`/`path` column you'll get a canonical mapping from the DB itself.

Always query `PRAGMA table_info('TableName')` to get column names and types for the DB you're examining — implementations sometimes change column names and types across revisions.

## Where the data comes from
- This project is derived from an upstream C# project. The `reference/` folder contains copies of the original C# files (e.g., `Database.cs`, `Downloader.cs`, `Model/*`). These are useful to map SQL columns to in-memory types and to understand business logic for data generation and interpretation.

## Important: time formats and conversions
Different systems and languages often store timestamps differently. Be careful when reading numeric time columns — verify the unit and epoch before converting.

Common time encodings and how to convert them in Python:

- Unix epoch (seconds, integer or real) — common in many systems:

```python
from datetime import datetime, timezone
ts_seconds = 1700000000
dt = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
```

- Unix epoch (milliseconds) — often produced by JavaScript or DateTimeOffset.ToUnixTimeMilliseconds:

```python
ts_ms = 1700000000000
dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
```

- C# "ticks" (System.DateTime.Ticks) — 100-nanosecond intervals since year 0001-01-01 (the .NET "zero" DateTime). This is NOT the Unix epoch. Conversion example:

```python
from datetime import datetime, timedelta, timezone

# ticks: 100-nanosecond intervals since 0001-01-01
def datetime_from_csharp_ticks(ticks: int) -> datetime:
    epoch = datetime(1, 1, 1, tzinfo=timezone.utc)
    # 1 tick = 100 ns = 0.1 microsecond -> convert ticks to microseconds
    return epoch + timedelta(microseconds=(ticks / 10))

def csharp_ticks_from_datetime(dt: datetime) -> int:
    epoch = datetime(1, 1, 1, tzinfo=timezone.utc)
    delta = dt.astimezone(timezone.utc) - epoch
    # total seconds * 10_000_000 -> ticks (10^7)
    return int(delta.total_seconds() * 10_000_000)
```

Notes:
- If your C# code used `DateTime.Ticks` or `DateTime.UtcTicks`, use the above conversions (they use the 0001-01-01 epoch).
- If your C# code used `DateTimeOffset.ToUnixTimeSeconds()` or `ToUnixTimeMilliseconds()` then stored that value, treat it as Unix seconds or ms respectively (use the Unix conversions above).
- If you see very large integers like 6xxxxxxxxxxxxxx (16–17 digits), these are likely C# ticks; 10–13 digit values are usually Unix seconds/ms respectively.

### Examples & gotchas
- Example: a DB `ts` column contains `637800000000000000`. That looks like C# ticks. Use `datetime_from_csharp_ticks(...)` to convert.
- Example: a DB `ts` column contains `1700000000` → likely Unix seconds.
- Always check reference code where rows are read (e.g., `ReadMinutes`, `ReadDays` functions) to see exactly how the project decodes timestamp columns. The `reference/` C# sources show the canonical conversion the app uses.

## Best practices when scripting/inspecting
- Always open DBs read-only unless you know you must write.
- Use `PRAGMA table_info(...)` before assuming column names/types.
- Verify timestamps on a few rows and cross-check with known sample dates to determine epoch/units (e.g., check a row whose date you already know).
- Work in UTC when possible to avoid timezone confusion. If the DB stores local times, the reference code often also stores a timezone/offset field in `SymbolInfo` or similar.
- If you need to re-create or transform data, prefer extracting to CSV/Parquet and doing transformations on copies.

## Reference pointers (where to look in this workspace)
- `2025 review/database/reference/` — copies of the original C# files (look for `Database.cs`, `Download/*`, and `Model/*`) to find the exact column-to-field mappings and conversion code.
- In the original project these functions are typically named `ReadDays`, `ReadMinutes`, `ReadSymbolInfo`, `ReadEarnings` — search `Database.cs` for those methods to see exact logic.

## Quick-check checklist before using data
- Verify you opened the DB read-only (or copied it first).
- Run `PRAGMA table_info('Days')` (or the table you're using).
- Inspect a few rows and determine whether timestamp values look like Unix seconds, Unix ms, or C# ticks.
- Convert a sample timestamp using the appropriate snippet above and ensure the resulting date matches expectations.

----
If you'd like, I can:
- extract a small sample (first 20 rows) from the specific DB file you point me at, or
- open `reference/Database.cs` here and paste the exact read-time conversion lines so we can lock the conversion strategy to the project code.

Make a selection and I'll proceed.

