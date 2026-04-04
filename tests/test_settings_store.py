import unittest
from unittest.mock import MagicMock, patch

from sellmanagement.gui.settings_store import get_client_id, set_client_id


class TestClientIdSettings(unittest.TestCase):
    def test_roundtrip_via_mock_settings(self):
        data: dict = {}

        inst = MagicMock()

        def _get(k, default=None):
            return data.get(k, default)

        def _set(k, v):
            data[k] = v

        inst.value.side_effect = _get
        inst.setValue = _set

        with patch("sellmanagement.gui.settings_store._settings", return_value=inst):
            self.assertEqual(get_client_id(), 1)
            set_client_id(42)
            self.assertEqual(get_client_id(), 42)

    def test_get_client_id_clamps_invalid(self):
        data = {"ib/client_id": "not-int"}
        inst = MagicMock()
        inst.value.side_effect = lambda k, d=None: data.get(k, d)
        inst.setValue = lambda k, v: data.update({k: v})
        with patch("sellmanagement.gui.settings_store._settings", return_value=inst):
            self.assertEqual(get_client_id(), 1)


if __name__ == "__main__":
    unittest.main()
