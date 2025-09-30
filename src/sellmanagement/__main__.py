from .config import Config
from .ib_client import IBClient
from .assign import set_assignment, get_assignments_list
from .download_manager import persist_batch_daily
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



