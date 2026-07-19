import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from session_monitor import (
    SessionMonitor,
    WTS_SESSION_LOCK,
    WTS_SESSION_UNLOCK,
)


class SessionMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.api = Mock()
        self.api.register.return_value = True
        self.monitor = SessionMonitor(api=self.api)

    def tearDown(self):
        self.monitor.stop()
        self.monitor.close()

    def test_start_and_stop_register_exactly_once(self):
        self.assertTrue(self.monitor.start())
        self.assertTrue(self.monitor.start())

        self.assertTrue(self.monitor.is_registered)
        self.api.register.assert_called_once_with(int(self.monitor.winId()))

        self.monitor.stop()
        self.monitor.stop()

        self.assertFalse(self.monitor.is_registered)
        self.api.unregister.assert_called_once_with(int(self.monitor.winId()))

    def test_lock_and_unlock_events_update_state_and_emit_signals(self):
        states = []
        locked_events = []
        unlocked_events = []
        self.monitor.lock_state_changed.connect(states.append)
        self.monitor.locked.connect(lambda: locked_events.append(True))
        self.monitor.unlocked.connect(lambda: unlocked_events.append(True))

        self.assertTrue(self.monitor._handle_session_change(WTS_SESSION_LOCK))
        self.assertTrue(self.monitor.is_locked)
        self.assertTrue(self.monitor._handle_session_change(WTS_SESSION_UNLOCK))
        self.assertFalse(self.monitor.is_locked)

        self.assertEqual(states, [True, False])
        self.assertEqual(locked_events, [True])
        self.assertEqual(unlocked_events, [True])

    def test_duplicate_and_unrelated_events_do_not_emit_extra_signals(self):
        states = []
        self.monitor.lock_state_changed.connect(states.append)

        self.monitor._handle_session_change(WTS_SESSION_LOCK)
        self.assertTrue(self.monitor._handle_session_change(WTS_SESSION_LOCK))
        self.assertFalse(self.monitor._handle_session_change(12345))

        self.assertEqual(states, [True])

    def test_registration_failure_is_non_fatal(self):
        self.api.register.return_value = False

        self.assertFalse(self.monitor.start())

        self.assertFalse(self.monitor.is_registered)
        self.api.unregister.assert_not_called()


if __name__ == "__main__":
    unittest.main()
