import os
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import diagnostics


class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ntp_check_uses_protocol_query(self):
        with patch("diagnostics.TimeSyncService") as service_type:
            service_type.return_value._query_ntp.side_effect = [None, 0.25]

            server, reachable = diagnostics.check_ntp_servers([
                ("first.example", 123),
                ("second.example", 123),
            ])

        self.assertTrue(reachable)
        self.assertEqual(server, "second.example:123")
        self.assertEqual(service_type.return_value._query_ntp.call_count, 2)

    def test_async_callback_is_delivered_on_qt_thread(self):
        main_thread = threading.get_ident()
        received = []

        def fake_run(config_mgr, callback):
            callback("done", True, ["ok"])

        with patch("diagnostics.run_diagnostics", side_effect=fake_run):
            worker = diagnostics.run_diagnostics_async(
                callback=lambda *args: received.append(
                    (threading.get_ident(), args)
                )
            )
            worker.join(timeout=2)
            deadline = time.monotonic() + 2
            while not received and time.monotonic() < deadline:
                self.app.processEvents()

        self.assertEqual(received[0][0], main_thread)
        self.assertEqual(received[0][1], ("done", True, ["ok"]))


if __name__ == "__main__":
    unittest.main()
