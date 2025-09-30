from sellmanagement.ib_client import IBClient


def test_ib_client_connect_disconnect(monkeypatch):
    class DummyIB:
        def connect(self, host, port, clientId, timeout=10):
            return True

        def isConnected(self):
            return True

        def disconnect(self):
            return True

    monkeypatch.setattr('sellmanagement.ib_client.IB', DummyIB)
    client = IBClient()
    assert client.connect() is True
    client.disconnect()


