# T002 — Extract Interactive Prompts from `__main__.py`

## Metadata

| Field | Value |
|-------|-------|
| Task ID | T002 |
| Title | Extract interactive prompts from `__main__.py` |
| Status | OPEN |
| Priority | P1 |
| Created | 2026-04-04 |
| Session | S001 |
| Detail File | `docs/03-tasks/tracker/T002-extract-interactive-prompts.md` |

---

## 1. Goal

Extract all interactive `input()` prompts from `_cmd_start()` in `__main__.py` into a dedicated `cli_prompts.py` module, so `_cmd_start()` remains an orchestration layer and interactive logic is cleanly separated.

---

## 2. Background

The `_cmd_start` function in `__main__.py` (approx. 400 lines) mixes:
- IB connection setup
- Live position fetching
- Assignment CSV sync
- **Interactive MA assignment prompts** (`input()` calls)
- **Interactive order confirmation** (`input("CONFIRM transmit...")`)
- Minute loop scheduling
- Snapshot execution
- Signal generation
- Terminal output formatting

The `input()` calls block the loop and make the function impossible to test without a TTY. Extracting them into a dedicated module enables:
- Unit testing of business logic without interactive prompts
- Alternative interfaces (GUI, API) to reuse the same prompts
- Cleaner separation of concerns

---

## 3. Design

### New Module: `cli_prompts.py`

```
src/sellmanagement/
├── __main__.py          # orchestration only
├── cli_prompts.py       # NEW: all interactive prompt functions
```

### Functions to Extract

```python
def prompt_assignment(ticker: str, default_idx: int = 7) -> tuple[str, int, str]:
    """Prompt user to choose MA type/length/timeframe.
    Returns (ma_type, length, timeframe).
    Raises KeyboardInterrupt on Ctrl+C."""

def confirm_live_orders(tickers: list[str]) -> bool:
    """Print summary and ask for YES confirmation.
    Returns True only if user types YES exactly.
    Raises KeyboardInterrupt on Ctrl+C."""

def prompt_timeframe_for_ticker(ticker: str) -> str:
    """Ask user to select timeframe for a ticker (1H or D)."""
```

---

## 4. Open Questions

- Should the confirmation prompt display the tickers and quantities to be sold?
- Should there be a `--yes-to-all` flag that bypasses confirmation in live mode?
- Should the `input()` calls be replaced with a `TextIO` parameter so they can be unit-tested with `io.StringIO`?

---

## 5. Acceptance Criteria

- [ ] `cli_prompts.py` contains all `input()` calls from `_cmd_start`
- [ ] `_cmd_start` calls `cli_prompts.*` instead of calling `input()` directly
- [ ] Unit tests can mock the prompts with `unittest.mock.patch('builtins.input')`
- [ ] The `--yes-to-all` flag is added for scripted live runs
- [ ] `docs/05-reference/02-module-api.md` is updated to document `cli_prompts.py`
