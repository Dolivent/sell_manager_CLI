from .config import Config
from .ib_client import IBClient
import argparse


def main():
    parser = argparse.ArgumentParser(prog="sellmanagement")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default)")
    parser.add_argument("--live", action="store_true", help="Enable live mode (must be explicit)")
    parser.add_argument("--client-id", type=int, default=1)
    args = parser.parse_args()

    config = Config(dry_run=not args.live, client_id=args.client_id)
    ib = IBClient(host=config.host, port=config.port, client_id=config.client_id)
    connected = ib.connect()
    if not connected:
        print("Failed to connect to IB Gateway/TWS")
        return

    positions = ib.get_positions()
    print(f"Fetched {len(positions)} positions (dry-run={config.dry_run})")
    ib.disconnect()


if __name__ == "__main__":
    main()


