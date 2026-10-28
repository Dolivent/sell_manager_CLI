import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

import pytest
import logging

from sellmanagement.orders import prepare_close_order, execute_order


class BrokenPrepareClient:
    def prepare_order(self, *a, **k):
        raise RuntimeError('boom prepare')


def test_execute_order_handles_prepare_failure(caplog):
    caplog.set_level(logging.ERROR)
    client = BrokenPrepareClient()
    p = prepare_close_order('X:FAIL', 1)
    res = execute_order(client, p, dry_run=True)
    # even in dry-run we prepare; failure should return failed_prepare
    assert res['status'] == 'failed_prepare'
    assert 'Failed to prepare IB order' in caplog.text


class BrokenPlaceClient:
    def prepare_order(self, symbol, qty, otype):
        return None

    def positions(self):
        return []

    def openOrders(self):
        return []

    def place_order(self, *a, **k):
        raise RuntimeError('boom place')


def test_execute_order_handles_transmit_failure(caplog):
    caplog.set_level(logging.ERROR)
    client = BrokenPlaceClient()
    p = prepare_close_order('X:TO', 3)
    res = execute_order(client, p, dry_run=False)
    assert res['status'] == 'failed_transmit'
    assert 'Order transmit failed' in caplog.text


def test_execute_order_pre_submit_checks_logged(caplog):
    caplog.set_level(logging.INFO)
    class CheckClient:
        def prepare_order(self, *a, **k):
            return None

        def positions(self):
            return ['pos']

        def openOrders(self):
            return []

        def place_order(self, *a, **k):
            return {'status': 'placed'}

    client = CheckClient()
    p = prepare_close_order('X:CHK', 4)
    res = execute_order(client, p, dry_run=False)
    assert res['status'] == 'placed'
    assert 'Pre-submit checks' in caplog.text


