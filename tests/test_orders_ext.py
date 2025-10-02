import sys
from pathlib import Path

# Ensure tests can import the package when running in-editor/test runners
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

import pytest
from sellmanagement.orders import prepare_close_order, execute_order


class DummyIBClient:
    def __init__(self):
        self.place_called = False
        self.prepared_args = None

    def prepare_order(self, symbol, quantity, order_type):
        # return a simple prepared-like dict
        self.prepared_args = (symbol, quantity, order_type)
        return {'contract': 'C', 'order': 'O', 'symbol': symbol, 'quantity': quantity, 'order_type': order_type}

    def place_order(self, *args, **kwargs):
        self.place_called = True
        return {'status': 'placed', 'detail': 'ok'}

    def positions(self):
        return []

    def openOrders(self):
        return []


def test_execute_order_dry_run_never_places():
    dummy = DummyIBClient()
    p = prepare_close_order('NASDAQ:DRY', 5)
    res = execute_order(dummy, p, dry_run=True)
    assert res['status'] == 'simulated'
    assert dummy.place_called is False


def test_execute_order_live_places():
    dummy = DummyIBClient()
    p = prepare_close_order('NASDAQ:LIVE', 2)
    res = execute_order(dummy, p, dry_run=False)
    assert res['status'] == 'placed'
    assert dummy.place_called is True


