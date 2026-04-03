<!-- 170dbf14-80ea-4326-9531-41246764e380 a954e211-914b-45f2-bc8e-8de5a64bdf32 -->
# GUI PRD — sell_manager_CLI (updated)

## Goal (refined)

Provide an integrated desktop GUI (tkinter) for the existing CLI that: shows the current positions and minute-snapshot status, lets the user set/override assigned moving averages (persisted to `config/assigned_ma.csv`), view signals and traces, control live vs dry-run, and submit orders using either Market Sell or Stop-Market at the hourly-low strategy.

## Quick decisions incorporated

- GUI framework: `tkinter` (matches reference project and prior choice).
- Architecture: Integrated — GUI runs in the same Python process and uses the existing `IBClient` and business logic.
- Stop-order preference: **Stop-market at the exact low of the hourly bar that generated the sell signal** (user choice confirmed).

## New behavior / UX rules (user-requested changes)

- One-row action — "Execute Sell":
- Live mode: clicking the action transmits the sell immediately (no confirmation modal). The UI still shows a brief summary and the lifecycle result once completed.
- Dry-run mode: clicking the action shows a preview/confirmation modal with `prepare_close_order()` output and a simulated result (notification) when "Confirm" is pressed.
- Alternative sell strategy: add a UI toggle to select between two sell strategies per-account or per-order:
- **Market Sell** — default market close order (existing behavior).
- **Stop at Hourly Low (Stop-market)** — place a stop-market order where the stop price equals the low of the hourly bar that triggered the SellSignal.
- The strategy toggle is visible in the Positions tab (global selector at the top) and in the single-row order preview modal (overridable per-order).

## Required functional changes (high-level)

1. Persist/Expose Triggering Bar Low

- Enhance `src/sellmanagement/minute_snapshot.py` to include the triggering hourly bar low in each row when the assigned timeframe is hourly and a bar exists. Add field name `trigger_hourly_low` (float) to snapshot rows.

2. Orders support for stop-market

- Extend `src/sellmanagement/orders.py` (and possibly `order_manager.py`/`order_manager.place_and_finalize`) to prepare and place stop-market orders in addition to market orders. Add a `strategy` parameter to `prepare_close_order()` (e.g., `'MKT'` or `'STP'`) and for `'STP'` require a `stop_price` value.

3. UI behavior

- Positions tab: show a global strategy toggle (Market / Stop@HourlyLow) and per-row override. When Stop strategy chosen and the selected row lacks `trigger_hourly_low`, disable immediate execution and show an explanatory tooltip.
- Preview modal: displays `prepare_close_order()` output and the chosen strategy; when Live mode is ON and user clicks Execute, skip confirmation and transmit immediately (showing a non-blocking toast). In Dry-run, require explicit Confirm to simulate.

4. Safety & confirmation policies

- Live mode enabling still requires explicit enabling in Settings with a modal acknowledgement (risk warning). But individual order confirmation is skipped in Live mode per the user's request.
- Order results must surface lifecycle results in a modal/log; errors/incomplete states must be visible.

## Data mapping & logs

- `minute_snapshot` rows will now include `trigger_hourly_low` to support Stop@Low orders. The snapshot JSONL schema change is additive (backward-compatible).
- Signals and trace logs remain unchanged; orders lifecycle results will be appended to logs/UI but need not change file schema.

## UI screens and elements (updated)

- Positions Tab (default)
- Columns: ticker, assigned_ma, ma_value, last_close, distance_pct, position, avg_cost, last_bar_date, trigger_hourly_low, strategy_override, actions
- Global strategy toggle (Market / Stop@HourlyLow) with per-row override.
- Per-row actions: Preview/Execute Sell — behavior depends on Live/Dry and selected strategy.
- Preview/Execute modal
- Shows prepared order details from `prepare_close_order()` (order type, quantities, target price, stop price if applicable).
- Provides Confirm button (only used when Dry-run) or Execute button (in Live mode Execute sends immediately without confirmation). If strategy is Stop@HourlyLow, show the stop price and source (hourly low timestamp).
- Settings
- Live checkbox (persisted runtime or config) with required modal acknowledgement.

## Acceptance criteria (updated)

- Positions tab shows `trigger_hourly_low` for hourly-assigned tickers when available.
- User can choose global strategy Market / Stop@HourlyLow and override per-row.
- In Live mode, Execute sends orders immediately (market or stop-market) without a confirmation modal and shows lifecycle result.
- In Dry-run, Execute opens a preview that requires confirmation and only simulates sending (no real IB transmission).
- `config/assigned_ma.csv` updates from UI edits and refresh snapshot & UI immediately.

## Implementation tasks (todos) — updated

- gui_scaffold: Create `src/sellmanagement/gui/` package and scaffold `main_window.py` and tab modules.
- positions_tab: Implement Positions table with color coding and inline MA edit.
- assignments_editor: Add Assignments tab to edit and sync `config/assigned_ma.csv`.
- settings_ib: Add Settings tab with IB connect/disconnect and Live toggle.
- orders_ui: Implement order preview and execute dialogs wired to `prepare_close_order()` and `execute_order()`; implement Live vs Dry-run behavior (no confirmation in Live).
- logs_signals_tab: Add Logs/Signals tab to view `logs/*` files and signal history.
- cli_integration: Add `--gui` flag to `__main__.py` and minimal startup glue.
- minute_snapshot_trigger_low: Modify `run_minute_snapshot()` to compute and persist `trigger_hourly_low` when assignment timeframe is hourly and hourly bars are available.
- orders_support_stop: Extend `orders.py` (and `order_manager` if needed) to prepare/place stop-market orders using `stop_price` input.
- sell_strategy_toggle: Add UI global strategy toggle and per-row override in Positions tab.

## Testing & QA (updated)

- Unit tests for new `prepare_close_order(..., strategy='STP', stop_price=...)` behavior.
- Manual QA: verify Stop@Low orders are prepared with the correct stop price from snapshot data, and that Live sends immediately while Dry-run shows simulation.

### To-dos

- [ ] Create GUI package and scaffold main window and tabs
- [ ] Implement Positions table with color coding and inline MA edit
- [ ] Add Assignments tab to edit and sync `config/assigned_ma.csv`
- [ ] Add Settings tab with IB connect/disconnect and Live toggle
- [ ] Implement order preview and execute dialogs wired to `orders.py`
- [ ] Add Logs/Signals tab to view `logs/*` files and signal history
- [ ] Add `--gui` flag to `__main__.py` and minimal startup glue