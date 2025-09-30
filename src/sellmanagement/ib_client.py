from ib_insync import IB
from typing import List


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


