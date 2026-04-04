from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments_list, sync_assignments_to_positions
from .cli_executor import transmit_live_sell_signals
from .cli_loop import (
    heartbeat_cycle,
    print_last_signals_preview,
    print_snapshot_table,
    sleep_until_next_minute_ny,
    sort_snapshot_rows_for_display,
)
from .cli_prompts import confirm_live_transmit, prompt_ma_assignment
from .downloader import batch_download_daily, persist_batch_halfhours
from .cache import merge_bars
from datetime import datetime
from .log_config import setup_logging
from .minute_snapshot import run_minute_snapshot
import argparse
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
    yes_to_all = bool(getattr(args, "yes_to_all", False))

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

        try:
            print_last_signals_preview(Path(_signals_log_path().resolve()))
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

            for tk in need_assign:
                try:
                    fam, ln, tf = prompt_ma_assignment(tk)
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
        from .trace import append_trace
        from zoneinfo import ZoneInfo

        last_wake = None
        heartbeat_interval = 60.0

        while True:
            sleep_until_next_minute_ny()
            last_wake = heartbeat_cycle(
                last_wake, append_trace, heartbeat_interval=heartbeat_interval
            )

            try:
                append_trace(
                    {
                        "event": "heartbeat",
                        "ts": datetime.now(tz=ZoneInfo("America/New_York")).isoformat(),
                    }
                )
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

                                for tk in need_assign:
                                    try:
                                        fam, ln, tf = prompt_ma_assignment(tk)
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
                                if confirm_live_transmit(assume_yes=yes_to_all):
                                    transmit_live_sell_signals(ib, gen, snapshot_ts=ts or "")
                                else:
                                    print('Live transmit aborted by user; no orders sent')
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        append_trace({"event": "signal_evaluation_failed", "error": str(e)})
                    except Exception:
                        pass
                rows = sort_snapshot_rows_for_display(rows)
                print_snapshot_table(rows)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.exception("Minute snapshot iteration failed: %s", e)
                print(f"Minute snapshot failed: {e}")
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        ib.disconnect()


def _cmd_dashboard(args: argparse.Namespace) -> None:
    from .dashboard import run_dashboard

    run_dashboard(host=args.host)


def _cmd_ma_export(args: argparse.Namespace) -> None:
    from .assign import export_assignments_json

    export_assignments_json(args.path)
    logger.info("Exported MA preset to %s", args.path)


def _cmd_ma_import(args: argparse.Namespace) -> None:
    from .assign import import_assignments_json

    summary = import_assignments_json(args.path, merge=bool(args.merge))
    logger.info("Imported MA preset mode=%s count=%s", summary.get("mode"), summary.get("count"))


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
    p_start.add_argument(
        "--yes-to-all",
        action="store_true",
        help="With --live, skip the interactive YES confirmation (for scripted runs only).",
    )
    p_start.add_argument("--client-id", type=int, default=1)
    p_start.add_argument("--gui", action="store_true", help="Launch the GUI instead of running the CLI")

    # metrics and retry commands removed in simplified mode

    p_dash = sub.add_parser(
        "dashboard",
        help="Read-only web UI for latest minute snapshot and signal batch (requires [gui] extra for Flask)",
    )
    p_dash.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default 127.0.0.1). Port from SELLMANAGEMENT_DASHBOARD_PORT or 5055.",
    )

    p_ma_exp = sub.add_parser("ma-export", help="Export assigned_ma.csv to a JSON preset file")
    p_ma_exp.add_argument("path", help="Output .json path")

    p_ma_imp = sub.add_parser("ma-import", help="Import a JSON preset into assigned_ma.csv")
    p_ma_imp.add_argument("path", help="Input .json path")
    p_ma_imp.add_argument(
        "--merge",
        action="store_true",
        help="Upsert by ticker instead of replacing the entire CSV",
    )

    # assign command: sellmanagement assign TICKER TYPE LENGTH
    p_assign = sub.add_parser("assign", help="Assign an MA to a ticker and persist to CSV")
    p_assign.add_argument("ticker", help="Ticker token in [exchange]:[ticker] format, e.g. NASDAQ:AAPL")
    p_assign.add_argument("type", help="MA type: SMA or EMA")
    p_assign.add_argument("length", help="MA length (integer)")
    p_assign.add_argument("--timeframe", default="1H", help="Timeframe for MA (e.g. 1H or D). Default: 1H")

    args = parser.parse_args(argv)
    setup_logging()

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
    elif cmd == "ma-export":
        _cmd_ma_export(args)
    elif cmd == "ma-import":
        _cmd_ma_import(args)
    elif cmd == "dashboard":
        _cmd_dashboard(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()



