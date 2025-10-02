import sys
from types import SimpleNamespace
from sellmanagement.ib_client import IBClient


def test_ib_client_connect_disconnect(monkeypatch):
    # Inject a fake `ib_insync` module with an `IB` class to ensure no network calls
    class DummyIB:
        def connect(self, host, port, clientId, timeout=10):
            return True

        def isConnected(self):
            return True

        def disconnect(self):
            return True

    fake_mod = SimpleNamespace(IB=DummyIB)
    monkeypatch.setitem(sys.modules, 'ib_insync', fake_mod)

    client = IBClient()
    assert client.connect() is True
    client.disconnect()


