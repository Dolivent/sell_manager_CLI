from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments_list
from .download_manager import persist_batch_daily
from datetime import datetime
from .minute_snapshot import run_minute_snapshot
import argparse
from typing import Optional


def _cmd_start(args: argparse.Namespace) -> None:
    config = Config(dry_run=not getattr(args, 'live', False), client_id=getattr(args, 'client_id', 1))

    ib = IBClient(host=config.host, port=config.port, client_id=config.client_id)
    if not ib.connect():
        print("Failed to connect to IB Gateway/TWS")
        return

    # Determine tickers to fetch (from assignments list)
    try:
        rows = get_assignments_list()
        tickers = [r.get('ticker') for r in rows if r.get('ticker')]
    except Exception:
        tickers = []

    if not tickers:
        print("No tickers found in assignments; nothing to download.")
        ib.disconnect()
        return

    print(f"Downloading daily bars for {len(tickers)} tickers in batches...")
    try:
        persist_batch_daily(ib, tickers, batch_size=getattr(config, 'batch_size', 32), batch_delay=getattr(config, 'batch_delay', 6.0), duration="1 Y")
    except Exception as e:
        print(f"Batch download failed: {e}")

    # Start a continuous minute-aligned loop: run snapshot at top of every minute
    try:
        print("Entering minute snapshot loop. Press Ctrl+C to stop.")
        import time
        while True:
            # wait until next top of minute
            now = datetime.utcnow()
            seconds_till_next = 60 - now.second - (now.microsecond / 1_000_000)
            time.sleep(seconds_till_next)
            try:
                rows = run_minute_snapshot(ib, tickers, concurrency=getattr(config, 'batch_size', 32))
                # print table-like output: ticker | last_close | MA(value) | distance_pct
                print(f"\nMinute snapshot at {datetime.utcnow().isoformat()}")
                # formatted table: aligned columns
                hdr = f"{'ticker':20}{'last_close':>12}{'ma_value':>12}{'distance_pct':>14}{'assigned_ma':>16}{'tf':>6}"
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
                    print(f"{tk:20}{last_s:>12}{ma_s:>12}{dist_s:>14}{am:>16}{tf:>6}")
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
    p_start.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default)")
    p_start.add_argument("--live", action="store_true", help="Enable live mode (must be explicit)")
    p_start.add_argument("--client-id", type=int, default=1)

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



