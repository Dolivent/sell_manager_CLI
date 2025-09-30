from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments, sync_assignments
import argparse
from typing import Optional


def _cmd_start(args: argparse.Namespace) -> None:
    config = Config(dry_run=not getattr(args, 'live', False), client_id=getattr(args, 'client_id', 1))
    # start async bridge first so we only use one IB connection (bridge is authoritative)
    bridge = None
    try:
        from .async_ib_bridge import AsyncIBBridge
        # try a small range of client ids to avoid "clientId already in use" issues
        start_id = int(getattr(config, 'client_id', 1) or 1)
        bridge_connected = False
        for cid_offset in range(0, 8):
            try_id = start_id + cid_offset
            try:
                b = AsyncIBBridge(host=config.host, port=config.port, client_id=try_id)
                b.start(wait_timeout=6.0)
                # check if connected
                if getattr(b, 'ib', None) is not None and getattr(b.ib, 'isConnected', lambda: False)():
                    bridge = b
                    config.client_id = try_id
                    bridge_connected = True
                    break
                else:
                    try:
                        b.stop()
                    except Exception:
                        pass
            except Exception:
                # try next id
                continue
        if not bridge_connected:
            bridge = None
    except Exception:
        bridge = None

    ib = IBClient(host=config.host, port=config.port, client_id=config.client_id)
    # attach bridge so IBClient.connect can use bridge's connection instead of opening another
    try:
        if bridge is not None:
            setattr(ib, '_bridge', bridge)
    except Exception:
        pass
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

        # shared download manager to avoid recreating per-ticker
        try:
            from .download_manager import DownloadManager
            from .cache import persist_bars
            dm = DownloadManager(ib, concurrency=8)
        except Exception:
            dm = None

        def fetch_daily(ticker: str):
            rows = load_bars(f"{ticker}:1d")
            closes = _extract_closes(rows)
            if closes:
                return closes
            # cache empty -> request from IB via shared DownloadManager and persist
            try:
                if dm is None:
                    return []
                drows = dm.download_daily(ticker)
                if drows:
                    persist_bars(f"{ticker}:1d", drows)
                    return _extract_closes(drows)
            except Exception:
                pass
            return []

        def fetch_hourly(ticker: str):
            # try 1h cache first
            rows = load_bars(f"{ticker}:1h")
            closes = _extract_closes(rows)
            if closes:
                return closes
            # try half-hour cache
            halfs = load_bars(f"{ticker}:30m")
            if halfs:
                # aggregate 30m -> hourly by taking every second bar's close when possible
                vals = _extract_closes(halfs)
                if not vals:
                    return []
                hours = []
                for i in range(1, len(vals), 2):
                    hours.append(vals[i])
                if hours:
                    return hours
                return [vals[-1]]

            # if still empty, request from IB via DownloadManager and persist
            try:
                if dm is None:
                    return []
                hrows = dm.download_halfhours(ticker)
                if hrows:
                    persist_bars(f"{ticker}:30m", hrows)
                    vals = _extract_closes(hrows)
                    hours = []
                    for i in range(1, len(vals), 2):
                        hours.append(vals[i])
                    if hours:
                        return hours
                    return [vals[-1]] if vals else []
            except Exception:
                pass
            return []

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
            # create a background download queue so updater isn't blocked by network
            try:
                from .download_manager import DownloadQueue
                # start async bridge for reliable async calls
                try:
                    from .async_ib_bridge import AsyncIBBridge
                    bridge = AsyncIBBridge(host=config.host, port=config.port, client_id=config.client_id)
                    bridge.start()
                except Exception:
                    bridge = None

                dlq = DownloadQueue(ib, workers=config.download_workers, concurrency=config.download_concurrency)
                dlq._bridge = bridge
                # configure batch params
                try:
                    dlq._batch_size = int(config.batch_size)
                    dlq._batch_delay = float(config.batch_delay)
                except Exception:
                    pass
            except Exception:
                dlq = None

            def fetch_daily(ticker: str):
                rows = load_bars(f"{ticker}:1d")
                closes = _extract_closes(rows)
                if closes:
                    return closes
                # enqueue download and return empty (worker will persist)
                try:
                    if dlq is not None:
                        dlq.enqueue(ticker, kind='daily')
                except Exception:
                    pass
                return []

            def fetch_hourly(ticker: str):
                rows = load_bars(f"{ticker}:1h")
                closes = _extract_closes(rows)
                if closes:
                    return closes
                halfs = load_bars(f"{ticker}:30m")
                if halfs:
                    vals = _extract_closes(halfs)
                    hours = []
                    for i in range(1, len(vals), 2):
                        hours.append(vals[i])
                    if hours:
                        return hours
                    return [vals[-1]] if vals else []
                try:
                    if dlq is not None:
                        dlq.enqueue(ticker, kind='half')
                except Exception:
                    pass
                return []

            upd = MinuteUpdater(fetch_daily, fetch_hourly, on_update_handler, tickers=tickers)
            upd.start()
            print("Minute updater and download queue started — running in background. Press Ctrl+C to exit.")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                upd.stop()
                if dlq is not None:
                    dlq.stop(wait=True)
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

    # metrics command: show queue/failure metrics
    p_metrics = sub.add_parser("metrics", help="Show download queue and failure metrics")

    # retry-failures command: re-enqueue failures and process them briefly
    p_retry = sub.add_parser("retry-failures", help="Retry failed downloads from failures log")
    p_retry.add_argument("--attempts", type=int, default=20, help="Max failures to requeue")

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
        # show simple metrics from files and config
        try:
            from .assign import get_assignments_list
            from .download_manager import DownloadQueue
            from pathlib import Path
            a_list = get_assignments_list()
            failures_path = (Path(__file__).resolve().parents[2] / 'config' / 'download_failures.jsonl')
            fcount = 0
            if failures_path.exists():
                try:
                    with failures_path.open('r', encoding='utf-8') as f:
                        fcount = sum(1 for _ in f)
                except Exception:
                    fcount = -1
            print(f"Assigned MA rows: {len(a_list)}")
            print(f"Recorded failures: {fcount}")
            # echo config batch settings
            try:
                from .config import Config
                # print default values
                print(f"Download workers: {Config.download_workers if hasattr(Config, 'download_workers') else 'N/A'}, concurrency: {Config.download_concurrency if hasattr(Config, 'download_concurrency') else 'N/A'}, batch_size: {Config.batch_size if hasattr(Config, 'batch_size') else 'N/A'}, batch_delay: {Config.batch_delay if hasattr(Config, 'batch_delay') else 'N/A'}")
            except Exception:
                pass
        except Exception as e:
            print(f"Failed to collect metrics: {e}")
    elif cmd == "retry-failures":
        try:
            from .download_manager import DownloadQueue
            from .config import Config
            dlq = DownloadQueue(IBClient(host='127.0.0.1', port=4001, client_id=1), workers=Config.download_workers, concurrency=Config.download_concurrency)
            summary = dlq.retry_failures(max_attempts=args.attempts)
            print(f"Retry summary: requeued={summary.get('requeued')} kept={summary.get('kept')} cleared={summary.get('cleared')}")
            # allow workers to process for a short time
            import time as _t
            _t.sleep(2)
            dlq.stop(wait=True)
        except Exception as e:
            print(f"retry-failures failed: {e}")
    elif cmd == "assign":
        _cmd_assign(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


