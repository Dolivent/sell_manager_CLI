import sys
from pathlib import Path

# Ensure tests can import the package when running in-editor/test runners
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

import pytest
from sellmanagement.ib_client import IBClient


def test_prepare_order_requires_live_ib():
    client = IBClient()
    with pytest.raises(RuntimeError):
        client.prepare_order('NVDA', 1)


def test_place_order_requires_live_ib():
    client = IBClient()
    with pytest.raises(RuntimeError):
        client.place_order('NVDA', 1, 'MKT')


