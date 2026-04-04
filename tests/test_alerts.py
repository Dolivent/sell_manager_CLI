import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import sellmanagement.alerts as alerts_mod


class TestAlerts(unittest.TestCase):
    def setUp(self):
        alerts_mod._warned_incomplete_smtp = False

    def tearDown(self):
        alerts_mod._warned_incomplete_smtp = False

    def test_send_smtp_skips_without_env_warns_once(self):
        log = logging.getLogger("sellmanagement.alerts")
        blank = {
            "SELLMANAGEMENT_SMTP_HOST": "",
            "SELLMANAGEMENT_ALERT_TO": "",
        }
        with patch.dict(os.environ, blank, clear=False):
            os.environ.pop("SELLMANAGEMENT_SMTP_PASS", None)
            os.environ.pop("SELLMANAGEMENT_SMTP_USER", None)
            with self.assertLogs(log, level="WARNING") as cm:
                self.assertFalse(alerts_mod.send_smtp_alert("subj", "body"))
                self.assertFalse(alerts_mod.send_smtp_alert("subj2", "body2"))
        self.assertEqual(len(cm.records), 1)
        self.assertIn("SELLMANAGEMENT_SMTP_HOST", cm.records[0].getMessage())

    def test_send_smtp_sends_when_configured(self):
        env = {
            "SELLMANAGEMENT_SMTP_HOST": "smtp.example.test",
            "SELLMANAGEMENT_SMTP_PORT": "587",
            "SELLMANAGEMENT_ALERT_TO": "ops@example.test",
        }
        mock_smtp = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_smtp
        mock_ctx.__exit__.return_value = None
        with patch.dict(os.environ, env, clear=False):
            with patch("sellmanagement.alerts.smtplib.SMTP", return_value=mock_ctx):
                self.assertTrue(alerts_mod.send_smtp_alert("Hello", "Line1\nLine2"))
        mock_smtp.send_message.assert_called_once()

    def test_order_transmit_needs_alert(self):
        self.assertFalse(alerts_mod.order_transmit_needs_alert({"status": "filled"}))
        self.assertFalse(alerts_mod.order_transmit_needs_alert({"status": "simulated"}))
        self.assertTrue(alerts_mod.order_transmit_needs_alert({"status": "failed_prepare"}))
        self.assertTrue(alerts_mod.order_transmit_needs_alert({"status": "timeout"}))

    def test_auth_requires_pass_key_when_user_set(self):
        env = {
            "SELLMANAGEMENT_SMTP_HOST": "h",
            "SELLMANAGEMENT_SMTP_USER": "u",
            "SELLMANAGEMENT_ALERT_TO": "t@x",
        }
        with patch.dict(os.environ, env, clear=False):
            # Remove PASS if present from other tests
            os.environ.pop("SELLMANAGEMENT_SMTP_PASS", None)
            self.assertFalse(alerts_mod.send_smtp_alert("s", "b"))


if __name__ == "__main__":
    unittest.main()
