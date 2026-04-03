# Snappy Symbols SQLite DB — developer guide

## Purpose

A concise, read-only guide for developers who need to consume the Symbols database created by Snappy from IBKR market data. It explains where files live, naming rules, table schemas, exact semantics of integer time fields, conversion formulas (C# -> what the integers represent), and comprehensive example SQL queries for common reads.

**CRITICAL:** These files are treated as read-only by the ecosystem. Do not write, vacuum, alter schema, or modify these files in-place; always work on a copied file if you need to run writes or vacuum.

---

## Key source references

- `Snappy/Data/Database.cs` — DB access helpers, file path & schema creation, read/write helpers.
- `Snappy/Model/TimeInterval.cs` — tick constants and UtcMinutes/UtcThreeMinutes/UtcHalfHours math.
- `Snappy/Model/Minute.cs`, `ThreeMinute.cs`, `HalfHour.cs` — mapping integer fields ↔ DateTime.
- `Snappy/Model/ExchangeTime.cs` — exchange-local ↔ UTC conversion helpers.
- `Snappy/InteractiveBrokers/Client.Read.cs` — parsing IBKR timestamps and shows the Unix epoch tick constant used when converting epoch timestamps.

Keep these file paths handy when implementing integrations or validating conversions.

---

## File locations & naming scheme

- Database directory root: the runtime path returned by `AppData.Snappy()` with a `Symbols` subfolder. In the code this is exposed as `Database.SymbolDirectory` and resolves to `Path.Join(AppData.Snappy().FullName, "Symbols")`.
- Per-exchange subdirectory: `<SymbolsRoot>/<EXCHANGE_ID>/` — the exchange identifier is `Exchange.Id` (upper-case form is used in directory names).
- File name for a symbol: `<SYMBOL>.sqlite3` (constructed by `Database.SymbolToFileName`). Example: `AAPL.sqlite3`.
- Reserved Windows file name handling: names that conflict with Windows reserved names get a trailing underscore before the extension, e.g. `CON_.sqlite3`.
- Full path helper: `Database.GetFilePath(SymbolKey key)` returns `Path.Join(SymbolDirectory.FullName, key.Exchange.Id, SymbolToFileName(key.Symbol))`.

Always use `Database.GetFilePath(...)` or `Connection.File(...)` (in `Database.cs`) to derive the correct path in code.

---

## Schema overview (tables of interest)

The database is a per-symbol SQLite file. Important tables:

- `Info` — symbol metadata:
  - Columns (partial): `Id`, `Exchange`, `Symbol`, `Currency`, `TimeZoneId`, `Name`, `Industry`, `Sector`, `ISIN`, `StockType`, `SecurityType`, `Description`, `SharesOutstanding`, `IpoDate`...
- `Days` — daily candles:
  - Columns: `Date INTEGER NOT NULL` (ExchangeDate int, see below), `Open REAL`, `High REAL`, `Low REAL`, `Close REAL`, `Volume INTEGER`, `AveragePrice REAL`, `TradeCount INTEGER`
  - `Date` represents an `ExchangeDate` integer (YYYYMMDD).
- `Minutes`, `ThreeMinutes`, `HalfHours` — intraday aggregated candles:
  - Columns: `Time INTEGER NOT NULL`, `Open REAL NOT NULL`, `High REAL NOT NULL`, `Low REAL NOT NULL`, `Close REAL NOT NULL`, `Volume INTEGER NOT NULL`, `AveragePrice REAL NOT NULL`, `TradeCount INTEGER NOT NULL`
  - `Time` uses the integer bucketing semantics documented below.
- `Earnings` — earnings rows:
  - Columns: `Date INTEGER`, `Time TEXT`, `Eps REAL`, `Revenue REAL`, ...

More auxiliary/tables exist, but the above are the ones most likely consumed by downstream apps.

---

## Exact semantics of integer time columns

All intraday `Time` columns are integers derived from .NET DateTime ticks, bucketed by a time interval unit (minute / three-minute / half-hour). The project centralizes tick math in `TimeInterval.cs`.

Unit definitions (from `Snappy/Model/TimeInterval.cs`):

- `TicksPerMinute = 60 * 1_000 * 10_000L` = 600_000_000 ticks
- `TicksPerThreeMinutes = 3 * TicksPerMinute` = 1_800_000_000 ticks
- `TicksPerHalfHour = 30 * TicksPerMinute` = 18_000_000_000 ticks

How integers are produced (C# writer-side):

- Minute-level `Time` is `Minute.UtcMinutes` which equals `(int)(utcTicks / TicksPerMinute)` where `utcTicks` is `DateTime.UtcTicks`.
- Three-minute `Time` is `ThreeMinute.UtcThreeMinutes` equals `(int)(utcTicks / TicksPerThreeMinutes)`.
- Half-hour `Time` is `HalfHour.UtcHalfHours` equals `(int)(utcTicks / TicksPerHalfHour)`.

How to reconstruct a UTC DateTime from the stored integer:

- ticks = stored_int * TicksPerUnit (e.g., for minutes multiply by `TicksPerMinute`)
- C# UTC DateTime (exact) = `new DateTime(ticks, DateTimeKind.Utc)`

Relation to Unix epoch (if you need Unix timestamps, epoch seconds, or integration with other languages):

- .NET DateTime uses ticks since year 0001-01-01. The Unix epoch (1970-01-01T00:00:00Z) corresponds to:
  - `UnixEpochTicks = 621355968000000000` (this constant is used in `Client.Read.cs` when converting raw unix seconds into DateTime).
- Convert .NET ticks to Unix seconds:
  - `unix_seconds = (ticks - UnixEpochTicks) / 10_000_000` (because 1 second = 10_000_000 ticks).
- Convert stored integer minute/three-minute/half-hour to unix seconds:
  - `unix_seconds = (stored_int * TicksPerUnit - UnixEpochTicks) / 10_000_000`
  - Example (minutes): `unix_seconds = (stored_minute_value * 600_000_000 - 621355968000000000) / 10_000_000`

Important notes:

- Integers in DB are the bucket index derived from UTC ticks (the code always converts exchange-local times to UTC before computing the integer). That means the stored `Time` is UTC-aligned buckets and not "local exchange wall-clock" integers.
- When reading or querying by local exchange time, the code converts the exchange-local time into the same integer representation (see `Minute.From(exchangeTime, exchangeTimeZone).UtcMinutes` and similar helpers) before forming SQL queries.

---

## Timezone and exchange-local times

- Exchange-local concept: the project models exchange-local times via `ExchangeTime` which is essentially a wall-clock time in the exchange time zone.
- Before writing intraday buckets, the code converts `ExchangeTime` into UTC DateTime using `ExchangeTime.Utc(TimeZoneInfo exchangeTimeZone)` or the `From` factory helpers (see `ExchangeTime.cs`) and then computes the integer bucket.
- For reading ranges by exchange-local time, the project converts the desired exchange times to UTC-derived integers using the same `From(...).Utc*` helpers and uses those integers as query parameters.

Example pattern used throughout `Database.cs`:

```csharp
command.Parameters.AddWithValue("from", Minute.From(fromExchangeTime, exchangeTimeZone).UtcMinutes);
command.Parameters.AddWithValue("to", Minute.From(toExchangeTime, exchangeTimeZone).UtcMinutes);
```

This guarantees queries align with how values were stored.

---

## Comprehensive SQL examples (recommended patterns)

Always prefer opening the SQLite file read-only. If tooling doesn't support read-only mode, make a file copy and query the copy.

- Read symbol metadata:

```sql
SELECT Id, Exchange, Symbol, Currency, TimeZoneId, Name FROM Info;
```

- Read minutes between two UTC-bucket integers (assume `@fromUtcMinutes` and `@toUtcMinutes` are prepared using the same math):

```sql
SELECT Time, Open, High, Low, Close, Volume, AveragePrice, TradeCount
  FROM Minutes
  WHERE Time BETWEEN @fromUtcMinutes AND @toUtcMinutes
  ORDER BY Time ASC;
```

- Read latest N minutes:

```sql
SELECT Time, Open, High, Low, Close, Volume
  FROM Minutes
  ORDER BY Time DESC
  LIMIT 240; -- last 240 minutes
```

- Read three-minute candles for a day (compute `@startThreeMinute`/`@endThreeMinute` using the same ThreeMinute.From(...).UtcThreeMinutes helper):

```sql
SELECT Time, Open, High, Low, Close, Volume
  FROM ThreeMinutes
  WHERE Time BETWEEN @startThreeMinute AND @endThreeMinute
  ORDER BY Time ASC;
```

- Read daily candles (Days table uses `Date` as ExchangeDate int YYYYMMDD):

```sql
SELECT Date AS Time, Open, High, Low, Close, Volume
  FROM Days
  WHERE Date BETWEEN @fromDateInt AND @toDateInt
  ORDER BY Date ASC;
```

- Quick range/min-max check pattern (used in code to compute DB ranges):

```sql
SELECT MIN(Time), Count(Time), MAX(Time) FROM Minutes WHERE Time BETWEEN @from AND @to;
```

Notes on parameters:

- `@from`/`@to` for intraday tables must be the integer bucket values (UtcMinutes / UtcThreeMinutes / UtcHalfHours) computed by your integration code using the same formulas.
- For daily queries use `ExchangeDate.ToInt()` representation (YYYYMMDD).

---

## Practical integration notes and recommendations

- Match the integer math exactly. The project uses the .NET tick math and fixed constants (`TicksPerMinute` etc.). Reimplement those formulas precisely in your consuming application to ensure alignment.
- Always treat `Days.Date` as an `ExchangeDate` integer (YYYYMMDD). Do not interpret it as Unix epoch.
- For any read-only analysis, prefer opening the DB file in read-only mode. If you must perform write operations or schema migrations for analysis, **copy** the `.sqlite3` file and perform write operations on the copy only.
- When building time ranges from exchange-local wall-clock times, convert them to UTC with the exchange `TimeZoneInfo` and then compute the integer buckets. This mirrors the code's `Minute.From(..., exchangeTimeZone).UtcMinutes` helpers.

---

## Troubleshooting & gotchas

- Journal files: if a symbol file is locked or throws `FileLoadException`, code sometimes retries with `OpenReadWrite` to resolve transient journal situations — but for external integrations, prefer using a copied file to avoid locking.
- Do not rely on the presence of every table — earlier versions of the app may have lacked tables; `Database.cs` contains migration paths (`Migrate.AddEarningsTable`, `Migrate.AddProfileColumns`) that the writer code runs when initializing. Do not run migrations on the production files from your integration.

---

## Quick reference: numeric constants

- `TicksPerMinute = 600_000_000`
- `TicksPerThreeMinutes = 1_800_000_000`
- `TicksPerHalfHour = 18_000_000_000`
- `UnixEpochTicks = 621355968000000000`

Reconstruction examples (C#):

```csharp
int storedUtcMinutes = /* read from DB */;
long ticks = (long)storedUtcMinutes * 600_000_000L;
DateTime utc = new DateTime(ticks, DateTimeKind.Utc);
// unix seconds:
long unixSeconds = (ticks - 621355968000000000L) / 10_000_000L;
```

---

## Deliverables & contact pointers

- This document (developer guide) — use as the single point-of-truth for consuming Symbols DB.
- For any ambiguity about time-zone handling or bucket math, consult:
  - `Snappy/Model/TimeInterval.cs`
  - `Snappy/Model/Minute.cs`, `ThreeMinute.cs`, `HalfHour.cs`
  - `Snappy/Model/ExchangeTime.cs`
  - `Snappy/Data/Database.cs`

If you need further examples (e.g., cross-language conversions or sample integration code in a specific language), request the language(s) you want. Note: do not modify DB files in-place.


