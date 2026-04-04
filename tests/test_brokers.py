import unittest

from sellmanagement.brokers import IBKRBroker, create_broker
from sellmanagement.ib_client import IBClient


class TestBrokers(unittest.TestCase):
    def test_create_broker_ibkr(self):
        b = create_broker("ibkr", client_id=7)
        self.assertIsInstance(b, IBKRBroker)
        self.assertEqual(b.client_id, 7)

    def test_ib_client_is_alias(self):
        self.assertIs(IBClient, IBKRBroker)

    def test_unknown_broker(self):
        with self.assertRaises(ValueError):
            create_broker("unknown")


if __name__ == "__main__":
    unittest.main()
