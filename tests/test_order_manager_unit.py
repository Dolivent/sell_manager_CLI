import time
from types import SimpleNamespace

from sellmanagement import order_manager


class FakeTrade:
    def __init__(self, filled_after=0):
        self._start = time.time()
        self.filled_after = filled_after

    def isDone(self):
        # become done after filled_after seconds
        return (time.time() - self._start) >= self.filled_after


class FakeIB:
    def __init__(self, filled_after=0):
        self.trade = FakeTrade(filled_after=filled_after)

    def place_order(self, prepared, transmit=True):
        return {'status': 'placed', 'trade': self.trade}

    def get_trade_status(self, trade):
        return 'filled' if trade.isDone() else 'pending'

    def openOrders(self):
        return []

    def positions(self):
        return []


def test_place_and_finalize_immediate_fill():
    fake = FakeIB(filled_after=0)
    prepared = {'symbol': 'NASDAQ:AAPL', 'quantity': 1, 'order_type': 'MKT'}
    res = order_manager.place_and_finalize(fake, prepared, timeout=2)
    assert res['status'] == 'filled'
    assert res['positions_after'] == []


