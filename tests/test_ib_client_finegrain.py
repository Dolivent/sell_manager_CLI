import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

import pytest

from sellmanagement.ib_client import IBClient


class DummyIB:
    def __init__(self):
        self.last_place = None

    def placeOrder(self, contract, order):
        self.last_place = (contract, order)
        return {'orderId': 123}


def test_place_order_with_prepared_dict(monkeypatch):
    client = IBClient()
    client._use_ib = True
    dummy = DummyIB()
    client._ib = dummy

    prepared = {'contract': 'C', 'order': type('O', (), {})()}
    res = client.place_order(prepared, transmit=False)
    assert res['status'] == 'placed'


def test_place_order_builds_when_token_passed(monkeypatch):
    # ensure prepare_order raises when _use_ib False
    client = IBClient()
    client._use_ib = True
    dummy = DummyIB()
    client._ib = dummy

    # monkeypatch prepare_order to a simple implementation
    def fake_prepare(token, qty, otype, **k):
        return {'contract': 'C2', 'order': type('O', (), {})(), 'symbol': token, 'quantity': qty, 'order_type': otype}

    client.prepare_order = fake_prepare
    res = client.place_order('TICK', 7, 'MKT')
    assert res['status'] == 'placed'


def test_place_order_raises_when_not_connected():
    client = IBClient()
    client._use_ib = False
    client._ib = None
    with pytest.raises(RuntimeError):
        client.place_order('T', 1, 'MKT')


