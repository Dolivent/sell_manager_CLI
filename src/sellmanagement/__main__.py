from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments, sync_assignments
import argparse
from typing import Optional


def _cmd_start(args: argparse.Namespace) -> None:
    config = Config(dry_run=not getattr(args, 'live', False), client_id=getattr(args, 'client_id', 1))
    ib = IBClient(host=config.host, port=config.port, client_id=config.client_id)
    connected = ib.connect()
    if not connected:
        print("Failed to connect to IB Gateway/TWS")
        return

    positions = ib.get_positions()
    print(f"Fetched {len(positions)} positions (dry-run={config.dry_run})")
    # after fetching positions, print assignments table
    try:
        from .assign import get_assignments_list

        rows = get_assignments_list()
        if rows:
            print("\nAssigned MAs:")
            # compute column widths
            hdr = ("Ticker", "Type", "Length", "Timeframe")
            widths = [len(h) for h in hdr]
            for r in rows:
                widths[0] = max(widths[0], len(r.get('ticker', '')))
                widths[1] = max(widths[1], len(r.get('type', '')))
                widths[2] = max(widths[2], len(str(r.get('length', ''))))
                widths[3] = max(widths[3], len(r.get('timeframe', '')))

            fmt = f"{{:<{widths[0]}}}  {{:<{widths[1]}}}  {{:>{widths[2]}}}  {{:<{widths[3]}}}"
            print(fmt.format(*hdr))
            print("-" * (sum(widths) + 6))
            for r in rows:
                print(fmt.format(r.get('ticker', ''), r.get('type', ''), str(r.get('length', '')), r.get('timeframe', '')))
    except Exception:
        pass
    # start minute updater to keep process running and recompute indicators
    try:
        from .updater import MinuteUpdater
        from .cache import load_bars
        from .indicators import simple_moving_average, exponential_moving_average
        from .signals import append_signal, decide

        def _extract_closes(rows):
            out = []
            for r in rows:
                try:
                    if isinstance(r, dict):
                        v = r.get('close') or r.get('Close') or r.get('ClosePrice') or r.get('closePrice')
                    else:
                        v = getattr(r, 'close', None) or getattr(r, 'Close', None)
                    if v is None:
                        continue
                    out.append(float(v))
                except Exception:
                    continue
            return out

        def fetch_daily(ticker: str):
            rows = load_bars(f"{ticker}:1d")
            return _extract_closes(rows)

        def fetch_hourly(ticker: str):
            # try 1h cache first, else aggregate 30m
            rows = load_bars(f"{ticker}:1h")
            if rows:
                return _extract_closes(rows)
            halfs = load_bars(f"{ticker}:30m")
            return _extract_closes(halfs)

        assignments_map = get_assignments()

        def on_update_handler(ticker, daily_vals, hourly_vals):
            try:
                assign = assignments_map.get(ticker.upper())
                if not assign:
                    return
                fam = assign.get('type', 'SMA')
                length = int(assign.get('length') or 0)
                timeframe = assign.get('timeframe', '1H')
                values = hourly_vals if timeframe == '1H' else daily_vals
                if not values:
                    return
                close = float(values[-1])
                # only evaluate at top of hour
                from datetime import datetime
                now = datetime.now()
                if now.minute != 0:
                    return
                dec = decide(close, fam, length, values)
                entry = {
                    'symbol': ticker,
                    'timeframe': timeframe,
                    'family': fam,
                    'length': length,
                    'close': close,
                    'ma': dec.get('ma_value'),
                    'decision': dec.get('decision'),
                }
                append_signal(entry)
            except Exception:
                pass

        tickers = [r.get('ticker') for r in get_assignments_list()]
        if tickers:
            upd = MinuteUpdater(fetch_daily, fetch_hourly, on_update_handler, tickers=tickers)
            upd.start()
            print("Minute updater started — running in background. Press Ctrl+C to exit.")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                upd.stop()
                print("Stopped.")
    except Exception:
        pass
    # report any missing assigned-MA entries; do NOT modify the CSV automatically
    try:
        normalized = ib.get_latest_positions_normalized()
        assignments = get_assignments()
        missing = []
        for p in normalized:
            token = (p.get('token') or '').strip()
            if not token:
                continue
            if token.upper() not in assignments:
                missing.append(token)
        if missing:
            print("Some positions are missing assigned MAs. Let's assign them interactively.")
            # present numbered combinations of (MA family, timeframe, length)
            families = ["SMA", "EMA"]
            timeframes = ["1H", "D"]
            lengths = [5, 10, 20, 50, 100, 150, 200]
            combos = []
            for fam in families:
                for tf in timeframes:
                    for L in lengths:
                        combos.append((fam, tf, L))

            for tok in missing:
                while True:
                    try:
                        print(f"\nTicker: {tok}")
                        print("Select MA assignment from the numbered list:")
                        for i, (fam, tf, L) in enumerate(combos, start=1):
                            print(f"  {i:2d}) {fam}({L}) {tf}")
                        sel = input("Enter number for selection (default 14 -> SMA(50) 1H): ").strip()
                        if sel == "":
                            idx = 14  # default index maps to SMA(50) 1H (families order ensures this)
                        else:
                            idx = int(sel)
                        if idx < 1 or idx > len(combos):
                            raise ValueError("selection out of range")
                        fam, tf, L = combos[idx - 1]
                        set_assignment(tok, fam, int(L), timeframe=tf)
                        print(f"Assigned {tok} -> {fam}({L}) {tf}")
                        break
                    except Exception as e:
                        print(f"Invalid input: {e}. Please try again.")
    except Exception:
        pass
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
    elif cmd == "assign":
        _cmd_assign(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


