# Audit: signals & minute-snapshots — backup vs current

This report documents a static comparison between the backup pre-GUI CLI
version (folder: `docs/sell_manager_CLI - backup pre 20251206/src/`) and the
current workspace (`src/`). The focus was on:

- Moving-average (MA) calculation
- Signal generation logic
- Minute-level snapshot creation
- Adjacent features that could affect results (assignments/config, aggregation, cache)

Summary of results
- Critical discrepancy: `config/assigned_ma.csv` changed for some tickers (different MA lengths) — this will change MA values and therefore signals.
- High discrepancy: `sync_assignments_to_positions` in `assign.py` now includes a symbol-only fallback mapping that may result in different assignment mappings for some tickers.
- No discrepancies: core MA algorithms (SMA/EMA) and the runtime decision logic in `signals.py` / `signal_generator.py` are functionally identical between backup and current.
- Minor: code comments and small UI additions exist in GUI modules but do not change core calculation logic.

Methodology
- Located MA-related implementations: `indicators.py` (SMA/EMA and series helpers).
- Located signal decision path: `signals.decide` and `signal_generator.generate_signals_from_rows`.
- Located snapshot generation: `minute_snapshot.run_minute_snapshot`.
- Compared implementations across the two trees and inspected `config/assigned_ma.csv` from both trees.
- Produced concrete code excerpts for confirmed differences.

Findings (with examples)

1) Critical — Config: `assigned_ma.csv` changed (will change MA values)

Backup (`docs/.../config/assigned_ma.csv`)

```text
ticker,type,length,timeframe
NASDAQ:SERV,SMA,20,1H
NASDAQ:RR,SMA,20,1H
NYSE:CRCL,SMA,20,1H
NYSE:PL,SMA,20,1H
NASDAQ:ONDS,SMA,20,1H
```

Current (`config/assigned_ma.csv`)

```text
ticker,type,length,timeframe
NASDAQ:SERV,SMA,20,1H
NYSE:PL,SMA,20,1H
NASDAQ:RR,SMA,20,1H
NYSE:CRCL,SMA,50,1H
NASDAQ:ONDS,SMA,50,1H
```

Impact:
- For `NYSE:CRCL` and `NASDAQ:ONDS` the assigned MA length changed from 20 -> 50.
- MA value = SMA(close[-length:]) — changing `length` changes the MA numeric value and therefore the result of the comparison `close < ma_value` used for SellSignal decisions in `signals.decide` and `signal_generator`.
- Severity: Critical — signals produced for those tickers will differ whenever those tickers are evaluated.

Recommended action:
- Confirm whether the new assigned lengths are intentional. If not, restore the intended `assigned_ma.csv`.
- Add a test to assert that `assigned_ma.csv` changes are deliberate (or checked into a different branch).
- Add a unit/regression test that compares generated signals for a fixed snapshot dataset across versions.

2) High — Assignment mapping behavior changed: symbol-only fallback in `assign.sync_assignments_to_positions`

Backup excerpt (representative): `sync_assignments_to_positions` writes rows using exact existing assignments or leaves blanks for new tokens (no symbol-only fallback).

Current excerpt (new behavior present near `sync_assignments_to_positions`):

```python
# Try symbol-only fallback: if existing has an entry for the symbol without exchange, reuse it.
sym_only = t_up.split(":")[-1]
found = None
for ex_key, ex_val in existing.items():
    if ex_key.split(":")[-1] == sym_only:
        found = ex_val
        break
if found:
    rows.append({
        "ticker": t,
        "type": found.get("type", ""),
        "length": str(int(found.get("length") or 0)) if found.get("length") else "",
        "timeframe": found.get("timeframe", ""),
    })
    kept.append(t)
else:
    # new token: leave assignment blank for interactive flow
    rows.append({"ticker": t, "type": "", "length": "", "timeframe": ""})
    added.append(t)
```

Impact:
- When tokens provided to `sync_assignments_to_positions` are fully-qualified (`EXCHANGE:SYMBOL`) but existing assignments only have symbol-only variants or vice-versa, this code will re-use an existing assignment by symbol-only match. This can cause a ticker to pick up a different assignment than strictly expected by full-key match.
- Example: If existing assignment file has `SERV` (no exchange) and caller passes `NASDAQ:SERV`, the current code will reuse the existing row. That may differ from backup behavior where only exact `EXCHANGE:SYMBOL` keys were matched.
- Severity: High — mapping differences can cause use of different MA length/type/timeframe and therefore different signals.

Recommended action:
- If symbol-only fallback is intended, document it in `assign.py` and in the configuration process. Consider making it an explicit option (opt-in) to avoid surprise behavior.
- Add unit tests for `sync_assignments_to_positions` to assert behavior for exact match vs symbol-only fallback scenarios.

3) Low/None — Core MA calculation and signal logic

Examples showing identical implementations:

- `indicators.simple_moving_average` (both versions compute mean of last `length` values and return None if insufficient data).
- `indicators.exponential_moving_average` (same seeding + alpha).
- `signals.decide` and `signal_generator.generate_signals_from_rows` — both rely on `close < ma_value` comparison and both perform the same input validation and logging.

Relevant code excerpts (identical logic; shown for reference)

```python
def simple_moving_average(values: List[float], length: int) -> Optional[float]:
    if length <= 0:
        raise ValueError("length must be > 0")
    if not values or len(values) < length:
        return None
    window = values[-length:]
    return float(sum(window)) / float(length)
```

And:

```python
def decide(close: float, ma_type: str, length: int, values: List[float]) -> Dict[str, Any]:
    fam = (ma_type or "SMA").strip().upper()
    if fam == "EMA":
        ma_val = exponential_moving_average(values, length)
    else:
        ma_val = simple_moving_average(values, length)
    if ma_val is None:
        return {"decision": "Skip", "reason": "insufficient_data", "ma_value": None, "close": close}
    if float(close) < float(ma_val):
        return {"decision": "SellSignal", "ma_value": float(ma_val), "close": float(close)}
    else:
        return {"decision": "NoSignal", "ma_value": float(ma_val), "close": float(close)}
```

Impact summary and ranking
- Critical: `config/assigned_ma.csv` differences — immediate cause of different MA values and signals for affected tickers.
- High: `assign.sync_assignments_to_positions` symbol-only fallback — can change assignment mapping and therefore MA choice.
- Low: No code differences found in MA algorithm implementations or core decision logic.

Suggested remediation & tests
- Short-term (urgent):
  - Verify `config/assigned_ma.csv` with the product owner and either accept or revert changes. (Critical)
  - Add a regression test: for a canonical snapshot file (store in `tests/fixtures`), generate signals using the current code and compare to the backup's expected signals. Fail the CI if outputs diverge without an approved config change.
  - Add unit tests for `sync_assignments_to_positions` covering exact-match and symbol-only fallback cases.

- Medium-term:
  - Add a small CLI or script to diff `config/assigned_ma.csv` against a canonical file and warn on differences.
  - Make symbol-only fallback explicit (flag/option) rather than implicit behavior.

- Long-term:
  - Add integration tests that exercise `run_minute_snapshot()` + `generate_signals_from_rows()` on a recorded (mocked) IB data set to detect regressions automatically when GUI or other features touch upstream code.

Files inspected (representative)
- `docs/sell_manager_CLI - backup pre 20251206/src/sellmanagement/indicators.py`
- `docs/sell_manager_CLI - backup pre 20251206/src/sellmanagement/signal_generator.py`
- `docs/sell_manager_CLI - backup pre 20251206/src/sellmanagement/minute_snapshot.py`
- `docs/sell_manager_CLI - backup pre 20251206/src/sellmanagement/signals.py`
- `docs/sell_manager_CLI - backup pre 20251206/config/assigned_ma.csv`
- `src/sellmanagement/indicators.py`
- `src/sellmanagement/signal_generator.py`
- `src/sellmanagement/minute_snapshot.py`
- `src/sellmanagement/signals.py`
- `src/sellmanagement/assign.py`
- `config/assigned_ma.csv`

Next steps I will take if you want me to continue:
- (optional) With permission to execute code: run both versions against a canonical snapshot dataset and produce a per-ticker numeric diff (MA values and decisions).
- (optional) Add a regression test and CI check to prevent accidental config drift.

If you want me to proceed with execution-based verification, say "run comparisons" and provide any preferred small sample snapshot (or allow me to craft a synthetic dataset).




























