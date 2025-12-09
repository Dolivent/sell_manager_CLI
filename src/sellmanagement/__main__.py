from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments_list, sync_assignments_to_positions
from .downloader import batch_download_daily, persist_batch_halfhours
from .cache import merge_bars
from datetime import datetime, timedelta
from .minute_snapshot import run_minute_snapshot
import os
from .orders import prepare_close_order, execute_order
import argparse
from typing import Optional


def _cmd_start(args: argparse.Namespace) -> None:
    # Check if GUI mode is requested
    if getattr(args, 'gui', False):
        try:
            from .gui.run_gui import main as gui_main
            gui_main()
            return
        except ImportError as e:
            print(f"Failed to import GUI: {e}")
            print("Make sure GUI dependencies are installed: pip install qtpy PySide6")
            return
        except Exception as e:
            print(f"Failed to launch GUI: {e}")
            return

    config = Config(dry_run=not getattr(args, 'live', False), client_id=getattr(args, 'client_id', 1))

    use_rth_flag = not getattr(args, 'no_rth', False)
    ib = IBClient(host=config.host, port=config.port, client_id=config.client_id, use_rth=use_rth_flag)
    if not ib.connect():
        print("Failed to connect to IB Gateway/TWS")
        return

    # Print config file locations so user can open/edit them if desired
    try:
        from .assign import ASSIGNED_CSV
        from .signals import _log_path as _signals_log_path
        print(f"Assigned MA CSV: {ASSIGNED_CSV.resolve()}")
        print(f"Signals log: {_signals_log_path().resolve()}")

        # show last batch of signals (most-recent group by second) for quick startup visibility
        try:
            import json
            from pathlib import Path
            # reuse datetime already imported above; alias locally to avoid shadowing
            from datetime import datetime as _dt

            def _read_last_signal_batch(log_path: Path):
                if not log_path.exists():
                    return []
                groups = {}
                last_key = None
                with log_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        ts = obj.get("ts")
                        if not ts:
                            continue
                        try:
                            dt = _dt.fromisoformat(ts)
                            key = dt.replace(microsecond=0).isoformat()
                        except Exception:
                            key = ts.split(".")[0] if "." in ts else ts
                        groups.setdefault(key, []).append(obj)
                        last_key = key
                if not last_key:
                    return []
                return groups.get(last_key, [])

            try:
                lp = Path(_signals_log_path().resolve())
                last_batch = _read_last_signal_batch(lp)
                if last_batch:
                    print("\nLast signals (most recent batch):")
                    for s in last_batch:
                        try:
                            print(f"{s.get('ticker', '<unknown>'):20} -> {s.get('decision', '<undecided>')}")
                        except Exception:
                            continue
            except Exception:
                # best-effort display; do not interrupt startup on failure
                pass
        except Exception:
            pass
    except Exception:
        pass

    # Determine tickers to fetch (from assignments list) and sync with live positions
    try:
        rows = get_assignments_list()
        assigned_tickers = [r.get('ticker') for r in rows if r.get('ticker')]
    except Exception:
        assigned_tickers = []

    # fetch live positions and normalize to EXCHANGE:SYMBOL tokens
    try:
        live_positions = ib.positions()
        # positions() returns a list of Position(contract, position, avgCost) objects
        live_tickers = []
        parsed_positions = []
        for p in live_positions:
            try:
                contract = getattr(p, 'contract', None) or getattr(p, 'contract', None)
                if contract is None:
                    continue
                symbol = getattr(contract, 'symbol', None) or getattr(contract, 'localSymbol', None)
                exchange = getattr(contract, 'exchange', None) or 'SMART'
                position_size = getattr(p, 'position', None) or getattr(p, 'pos', None) or 0
                avg_cost = getattr(p, 'avgCost', None) or getattr(p, 'avg_cost', None)
                if symbol:
                    token = f"{exchange}:{symbol}"
                    live_tickers.append(token)
                    parsed_positions.append({
                        'ticker': token,
                        'position': float(position_size) if position_size is not None else 0.0,
                        'avgCost': float(avg_cost) if avg_cost is not None else None,
                    })
            except Exception:
                continue

        # print parsed positions to terminal
        print("\nFetched positions:")
        print(f"{'ticker':30}{'position':>12}{'avgCost':>12}")
        for r in parsed_positions:
            pos_s = '-' if r['position'] is None else f"{r['position']:.2f}"
            ac_s = '-' if r['avgCost'] is None else f"{r['avgCost']:.4f}"
            print(f"{r['ticker']:30}{pos_s:>12}{ac_s:>12}")
    except Exception:
        live_tickers = []

    # synchronize assignments file: keep existing assignments for tickers that are present in live_tickers,
    # add new tickers with blank assignment so user can assign later, and remove assignments for tickers no longer present.
    try:
        sync_result = sync_assignments_to_positions(live_tickers)
        tickers = live_tickers

        # show sync summary and current assignments to help debugging
        try:
            print('\nAssignment sync result:')
            print(sync_result)
            from .assign import get_assignments_list
            cur = get_assignments_list()
            print('\nCurrent assigned_ma.csv contents:')
            for r in cur:
                print(f"{r.get('ticker'):30}{r.get('type') or '-':>6}{str(r.get('length') or '-') :>8}{r.get('timeframe') or '-':>8}")
        except Exception:
            pass

        # determine tickers needing assignment: newly added OR existing rows with missing fields
        added = sync_result.get('added', [])
        cur_assignments = get_assignments_list()
        missing = []
        for r in cur_assignments:
            t = r.get('ticker')
            if not t:
                continue
            # consider missing if type empty or length missing/zero or timeframe empty
            if not (r.get('type') and r.get('length')) or not r.get('timeframe'):
                missing.append(t)

        # union of newly added and existing missing assignments (preserve order)
        need_assign = []
        for tk in added + missing:
            if tk not in need_assign:
                need_assign.append(tk)

        if need_assign:
            print('\nTickers requiring assignment:')
            for tk in need_assign:
                print(f" - {tk}")

            # build paired options: SMA on left, EMA on right for each length/timeframe
            lengths = [5, 10, 20, 50, 100, 150, 200]
            timeframes = ['1H', 'D']
            options = []
            for ln in lengths:
                for tf in timeframes:
                    options.append(('SMA', ln, tf))
                    options.append(('EMA', ln, tf))

            # default selection index for convenience (SMA,50,1H)
            try:
                default_idx = options.index(('SMA', 50, '1H')) + 1
            except Exception:
                default_idx = 1

            for tk in need_assign:
                try:
                    print(f"\nAssign MA for {tk}. Choose from the numbered list below (enter number, default {default_idx}):")
                    # print two columns per line (SMA left, EMA right)
                    for j in range(0, len(options), 2):
                        left_num = j + 1
                        right_num = j + 2
                        fam_l, ln_l, tf_l = options[j]
                        fam_r, ln_r, tf_r = options[j + 1]
                        left_label = f"{fam_l} {ln_l} {tf_l}"
                        right_label = f"{fam_r} {ln_r} {tf_r}"
                        print(f" {left_num:3d}) {left_label:16s} {right_num:3d}) {right_label}")

                    sel = input(f"Selection [default {default_idx}]: ").strip()
                    if not sel:
                        sel_idx = default_idx
                    else:
                        try:
                            sel_idx = int(sel)
                        except Exception:
                            sel_idx = default_idx
                    if sel_idx < 1 or sel_idx > len(options):
                        sel_idx = default_idx
                    fam, ln, tf = options[sel_idx - 1]
                    # persist assignment; timeframe is always present
                    set_assignment(tk, fam, int(ln), timeframe=tf)
                    print(f"Assigned {tk} -> {fam}({ln}) {tf}")
                except Exception as e:
                    print(f"Failed to assign for {tk}: {e}")
    except Exception:
        # fallback to assigned list if sync fails
        tickers = assigned_tickers

    if not tickers:
        print("No tickers found in assignments; nothing to download.")
        ib.disconnect()
        return

    print(f"Downloading daily bars for {len(tickers)} tickers in batches...")
    try:
        results = batch_download_daily(ib, tickers, batch_size=getattr(config, 'batch_size', 32), batch_delay=getattr(config, 'batch_delay', 6.0), duration="1 Y")
        # persist/merge daily results into cache
        for tk, rows in (results or {}).items():
            try:
                if rows:
                    merge_bars(f"{tk}:1d", rows)
            except Exception:
                continue
    except Exception as e:
        print(f"Batch download failed: {e}")

    # perform 30m backfill -> persist 30m and aggregated 1h caches
    try:
        print(f"Performing 30m backfill for {len(tickers)} tickers (this may take a while)...")
        # request 200 hourly bars -> 200 * 2 half-hour bars
        persist_batch_halfhours(ib, tickers, batch_size=getattr(config, 'batch_size', 8), batch_delay=getattr(config, 'batch_delay', 6.0), target_hours=200)
    except Exception as e:
        print(f"30m backfill failed: {e}")

    # Start a continuous minute-aligned loop: run snapshot at top of every minute
    try:
        print("Entering minute snapshot loop. Press Ctrl+C to stop.")
        import time
        from .trace import append_trace

        # Heartbeat/gap-detection: remember last wake time and detect large gaps
        # to handle sleep/screensaver/wake events. We log a regular heartbeat each
        # minute and a special "woke_late" event if we detect we've been paused.
        last_wake = None
        heartbeat_interval = 60.0

        while True:
            # wait until next top of minute (use America/New_York timezone)
            from zoneinfo import ZoneInfo
            now = datetime.now(tz=ZoneInfo('America/New_York'))
            # compute next minute boundary
            next_min = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
            # special-case: if next minute is 16:00 (4pm NY), wake 5 seconds earlier
            if next_min.hour == 16 and next_min.minute == 0:
                seconds_till_next = (next_min - now).total_seconds() - 5.0
            else:
                seconds_till_next = (next_min - now).total_seconds()
            if seconds_till_next < 0.1:
                seconds_till_next = 0.1

            # Sleep in small chunks so Ctrl+C is responsive
            slept = 0.0
            chunk = min(5.0, seconds_till_next)
            while slept + 0.0001 < seconds_till_next:
                to_sleep = min(chunk, seconds_till_next - slept)
                time.sleep(to_sleep)
                slept += to_sleep

            # detect wake/gap: compare wall-clock now to last_wake
            woke_at = datetime.now(tz=ZoneInfo('America/New_York'))
            if last_wake is None:
                last_wake = woke_at
            else:
                gap = (woke_at - last_wake).total_seconds()
                # If gap is significantly larger than heartbeat interval, we likely
                # resumed from sleep/screensaver. Log a special event with gap info.
                if gap > (heartbeat_interval * 1.5):
                    try:
                        append_trace({"event": "woke_late", "gap_seconds": gap, "reason": "suspiciously_large_gap"})
                    except Exception:
                        pass
                last_wake = woke_at

            # Emit a heartbeat trace so external monitors know process is alive
            try:
                append_trace({"event": "heartbeat", "ts": datetime.now(tz=ZoneInfo('America/New_York')).isoformat()})
            except Exception:
                pass

            try:
                # Before taking snapshot, refresh live positions and sync assignments
                try:
                    from .trace import append_trace
                    live_positions = ib.positions()
                    live_tickers = []
                    for p in live_positions:
                        try:
                            contract = getattr(p, 'contract', None) or getattr(p, 'contract', None)
                            if contract is None:
                                continue
                            symbol = getattr(contract, 'symbol', None) or getattr(contract, 'localSymbol', None)
                            exchange = getattr(contract, 'exchange', None) or 'SMART'
                            if symbol:
                                live_tickers.append(f"{exchange}:{symbol}")
                        except Exception:
                            continue
                    if live_tickers:
                        try:
                            # sync assignment file to current positions (preserve existing assignments)
                            sync_result = sync_assignments_to_positions(live_tickers)
                            append_trace({"event": "sync_assignments_before_snapshot", "summary": sync_result})

                            # If any newly added or previously-missing assignments exist, prompt the user
                            # interactively (same flow as startup) and persist selections immediately.
                            added = sync_result.get('added', [])
                            # read current canonical assignments to find missing/blank rows
                            from .assign import get_assignments_list
                            cur_assignments = get_assignments_list()
                            missing = []
                            for r in cur_assignments:
                                t = r.get('ticker')
                                if not t:
                                    continue
                                if not (r.get('type') and r.get('length')) or not r.get('timeframe'):
                                    missing.append(t)

                            # union of added + missing
                            need_assign = []
                            for tk in added + missing:
                                if tk not in need_assign:
                                    need_assign.append(tk)

                            if need_assign:
                                print('\nTickers requiring assignment (runtime):')
                                for tk in need_assign:
                                    print(f" - {tk}")

                                lengths = [5, 10, 20, 50, 100, 150, 200]
                                timeframes = ['1H', 'D']
                                options = []
                                for ln in lengths:
                                    for tf in timeframes:
                                        options.append(('SMA', ln, tf))
                                        options.append(('EMA', ln, tf))

                                try:
                                    default_idx = options.index(('SMA', 50, '1H')) + 1
                                except Exception:
                                    default_idx = 1

                                from .assign import set_assignment
                                for tk in need_assign:
                                    try:
                                        print(f"\nAssign MA for {tk}. Choose from the numbered list below (enter number, default {default_idx}):")
                                        for j in range(0, len(options), 2):
                                            left_num = j + 1
                                            right_num = j + 2
                                            fam_l, ln_l, tf_l = options[j]
                                            fam_r, ln_r, tf_r = options[j + 1]
                                            left_label = f"{fam_l} {ln_l} {tf_l}"
                                            right_label = f"{fam_r} {ln_r} {tf_r}"
                                            print(f" {left_num:3d}) {left_label:16s} {right_num:3d}) {right_label}")

                                        sel = input(f"Selection [default {default_idx}]: ").strip()
                                        if not sel:
                                            sel_idx = default_idx
                                        else:
                                            try:
                                                sel_idx = int(sel)
                                            except Exception:
                                                sel_idx = default_idx
                                        if sel_idx < 1 or sel_idx > len(options):
                                            sel_idx = default_idx
                                        fam, ln, tf = options[sel_idx - 1]
                                        set_assignment(tk, fam, int(ln), timeframe=tf)
                                        print(f"Assigned {tk} -> {fam}({ln}) {tf}")
                                    except Exception as e:
                                        print(f"Failed to assign for {tk}: {e}")

                            # restrict snapshot to live tickers to avoid acting on closed positions
                            tickers = live_tickers
                        except Exception as e:
                            append_trace({"event": "sync_assignments_failed", "error": str(e)})
                except Exception:
                    # best-effort: proceed even if positions sync fails
                    pass

                # run_minute_snapshot now returns (ts_iso_ny, rows)
                ts, rows = run_minute_snapshot(ib, tickers, concurrency=getattr(config, 'batch_size', 32))
                # parse snapshot timestamp (should be America/New_York aware ISO)
                try:
                    ts_dt = datetime.fromisoformat(ts)
                except Exception:
                    # fallback to current NY time
                    from zoneinfo import ZoneInfo
                    ts_dt = datetime.now(tz=ZoneInfo('America/New_York'))

                date_s = ts_dt.strftime('%Y-%m-%d')
                time_s = ts_dt.strftime('%H:%M:%S.%f')
                print("\nMinute snapshot at:")
                print(date_s)
                print(time_s)
                # trigger signal generator directly as a waterfall (use snapshot timestamp)
                try:
                    from .signal_generator import generate_signals_from_rows
                    from .trace import append_trace
                    # evaluate based on the snapshot timestamp
                    is_top_of_hour = (ts_dt.minute == 0)
                    is_eod_prep = (ts_dt.hour == 15 and ts_dt.minute == 59 and ts_dt.second >= 55)
                    evaluate_hourly = is_top_of_hour or is_eod_prep
                    evaluate_daily = is_eod_prep
                    if evaluate_hourly or evaluate_daily:
                        append_trace({"event": "signal_evaluation_start", "hourly": bool(evaluate_hourly), "daily": bool(evaluate_daily), "ts": ts})
                        gen = generate_signals_from_rows(rows, evaluate_hourly=evaluate_hourly, evaluate_daily=evaluate_daily, dry_run=bool(config.dry_run))
                        append_trace({"event": "signal_evaluation_done", "count": len(gen), "ts": datetime.now(tz=ts_dt.tzinfo).isoformat()})
                        try:
                            print(f"Signals generated: {len(gen)}")
                        except Exception:
                            pass

                        # If live mode requested, attempt to execute sell signals using IB client
                        try:
                            if not config.dry_run:
                                # one-time confirmation prompt to avoid accidental live orders
                                confirm = input('CONFIRM transmit live orders now? Type YES to proceed: ').strip()
                                if confirm == 'YES':
                                    # iterate generated signals and transmit sell orders for SellSignal entries
                                    for e in gen:
                                        try:
                                            if e.get('decision') == 'SellSignal':
                                                    # use the live position size included in the signal (if available)
                                                    pos = e.get('position')
                                                    try:
                                                        qty = int(abs(round(float(pos)))) if pos is not None else None
                                                    except Exception:
                                                        qty = None
                                                    if not qty or qty <= 0:
                                                        # nothing to close - skip transmitting
                                                        append_trace({'event': 'order_skipped', 'ticker': e.get('ticker'), 'reason': 'no_position', 'position': pos})
                                                        continue
                                                    # prepare close for full-size quantity
                                                    po = prepare_close_order(e.get('ticker'), qty, order_type='MKT')
                                                    # execute_order performs prepare->checks->place
                                                    res = execute_order(ib, po, dry_run=False)
                                                    append_trace({'event': 'order_attempt', 'ticker': e.get('ticker'), 'position': pos, 'qty': qty, 'result': str(res)})
                                        except Exception as ex:
                                            append_trace({'event': 'order_attempt_failed', 'ticker': e.get('ticker'), 'error': str(ex)})
                                else:
                                    print('Live transmit aborted by user; no orders sent')
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        append_trace({"event": "signal_evaluation_failed", "error": str(e)})
                    except Exception:
                        pass
                # formatted table: aligned columns
                # show rows with abv_be True first
                try:
                    # sort by abv_be (True first) then by distance_pct ascending within each group
                    def _sort_key(r):
                        # not bool(abv_be) -> False for True, True for False so True rows come first
                        abv_key = not bool(r.get('abv_be'))
                        # distance may be None; treat None as +inf so it sorts after numeric values
                        dist = r.get('distance_pct')
                        try:
                            dist_key = float(dist) if dist is not None else float('inf')
                        except Exception:
                            dist_key = float('inf')
                        return (abv_key, dist_key)

                    rows = sorted(rows, key=_sort_key)
                except Exception:
                    pass
                hdr = f"{'ticker':20}{'last_close':>12}{'ma_value':>12}{'distance_pct':>14}  {'assigned_ma':>18}{'abv_be':>8}"
                print(hdr)
                for r in rows:
                    tk = r.get('ticker') or ''
                    last_close = r.get('last_close')
                    ma_value = r.get('ma_value')
                    distance = r.get('distance_pct')

                    if last_close is None:
                        last_s = '-' 
                    else:
                        try:
                            last_s = f"{float(last_close):.2f}"
                        except Exception:
                            last_s = str(last_close)

                    if ma_value is None:
                        ma_s = '-'
                    else:
                        try:
                            ma_s = f"{float(ma_value):.2f}"
                        except Exception:
                            ma_s = str(ma_value)

                    if distance is None:
                        dist_s = '-'
                    else:
                        try:
                            dist_s = f"{float(distance):.1f}%"
                        except Exception:
                            dist_s = str(distance)

                    am = r.get('assigned_ma') or '-'
                    tf = r.get('assigned_timeframe') or '-'
                    # move timeframe in front of assigned_ma and drop separate tf column
                    assigned_display = f"{tf} {am}" if am and tf else (am or '-')
                    abv_be_val = r.get('abv_be')
                    if abv_be_val is None:
                        abv_s = '-'
                    else:
                        abv_s = 'T' if bool(abv_be_val) else 'F'
                    print(f"{tk:20}{last_s:>12}{ma_s:>12}{dist_s:>14}  {assigned_display:>18}{abv_s:>8}")
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Minute snapshot failed: {e}")
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        ib.disconnect()


def _cmd_assign(args: argparse.Namespace) -> None:
    ticker: str = args.ticker
    ma_type: str = args.type
    length: int = int(args.length)
    try:
        set_assignment(ticker, ma_type, length)
        print(f"Assigned {ticker} -> {ma_type.upper()}({length}) in config/assigned_ma.csv")
    except Exception as e:
        print(f"Failed to assign MA: {e}")


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(prog="sellmanagement")
    sub = parser.add_subparsers(dest="command")

    # start command (default behavior)
    p_start = sub.add_parser("start", help="Start the sellmanagement service")
    p_start.add_argument("--no-rth", action="store_true", help="Do not restrict historical requests to regular trading hours")
    p_start.add_argument("--live", action="store_true", help="Enable live mode (must be explicit). When enabled, an interactive confirmation is required before transmitting orders.")
    p_start.add_argument("--client-id", type=int, default=1)
    p_start.add_argument("--gui", action="store_true", help="Launch the GUI instead of running the CLI")

    # metrics and retry commands removed in simplified mode

    # assign command: sellmanagement assign TICKER TYPE LENGTH
    p_assign = sub.add_parser("assign", help="Assign an MA to a ticker and persist to CSV")
    p_assign.add_argument("ticker", help="Ticker token in [exchange]:[ticker] format, e.g. NASDAQ:AAPL")
    p_assign.add_argument("type", help="MA type: SMA or EMA")
    p_assign.add_argument("length", help="MA length (integer)")
    p_assign.add_argument("--timeframe", default="1H", help="Timeframe for MA (e.g. 1H or D). Default: 1H")

    args = parser.parse_args(argv)

    # Default to start when no command provided
    cmd = args.command or "start"
    if cmd == "start":
        _cmd_start(args)
    elif cmd == "metrics":
        print("Metrics command not available in simplified mode.")
    elif cmd == "retry-failures":
        print("retry-failures not available in simplified mode.")
    elif cmd == "assign":
        _cmd_assign(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()



