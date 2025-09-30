from ib_insync import IB
from typing import List
from typing import Optional


class IBClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 4001, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()

    def connect(self) -> bool:
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=10)
            return self.ib.isConnected()
        except Exception:
            return False

    def get_positions(self) -> List:
        return self.ib.positions()

    def get_open_orders(self):
        return self.ib.openOrders()

    def disconnect(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    def get_latest_positions_normalized(self) -> List[dict]:
        """Return a list of normalized position dicts from the IB client snapshot.

        Each dict contains keys: `exchange`, `symbol`, `token`, `quantity`, `avg_cost`, `raw`.
        This is a best-effort normalizer that tolerates different position object shapes.
        """
        out: List[dict] = []
        try:
            positions = list(self.get_positions() or [])
        except Exception:
            positions = []

        for pv in positions:
            try:
                contract = getattr(pv, 'contract', None) or getattr(pv, 'Contract', None)
                qty = None
                avg = 0.0
                if contract is None and isinstance(pv, (list, tuple)) and len(pv) >= 2:
                    contract = pv[0]
                    qty = pv[1]
                if qty is None:
                    qty = getattr(pv, 'position', None) or getattr(pv, 'Position', None) or 0
                try:
                    avg = getattr(pv, 'avgCost', None) or getattr(pv, 'AvgCost', None) or getattr(pv, 'averageCost', None) or 0.0
                except Exception:
                    avg = 0.0
                symbol = None
                exchange = None
                if contract is not None:
                    symbol = getattr(contract, 'symbol', None) or getattr(contract, 'Symbol', None)
                    exchange = getattr(contract, 'exchange', None) or getattr(contract, 'Exchange', None) or 'SMART'
                else:
                    symbol = getattr(pv, 'symbol', None) or getattr(pv, 'Symbol', None)
                    exchange = getattr(pv, 'exchange', None) or getattr(pv, 'Exchange', None) or 'SMART'

                token = f"{exchange}:{symbol}" if symbol else "<unknown>"
                out.append({'exchange': exchange, 'symbol': symbol, 'token': token, 'quantity': qty or 0, 'avg_cost': avg or 0.0, 'raw': pv})
            except Exception:
                # best-effort fallback
                try:
                    out.append({'exchange': 'UNKNOWN', 'symbol': None, 'token': '<unknown>', 'quantity': 0, 'avg_cost': 0.0, 'raw': pv})
                except Exception:
                    pass
        return out


