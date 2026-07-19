import os
import unittest
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from single_instance import SingleInstanceGuard


class SingleInstanceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.server_name = f"DesktopPet.Test.{uuid4().hex}"
        self.guards = []

    def tearDown(self):
        for guard in reversed(self.guards):
            guard.release()
        self.app.processEvents()

    def create_guard(self):
        guard = SingleInstanceGuard(self.server_name)
        self.guards.append(guard)
        return guard

    def test_second_instance_exits_and_activates_first(self):
        first = self.create_guard()
        second = self.create_guard()
        activations = []
        first.activation_requested.connect(lambda: activations.append(True))

        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        QTest.qWait(50)

        self.assertEqual(activations, [True])

    def test_lock_can_be_acquired_after_first_instance_releases(self):
        first = self.create_guard()
        replacement = self.create_guard()

        self.assertTrue(first.acquire())
        first.release()

        self.assertTrue(replacement.acquire())


if __name__ == "__main__":
    unittest.main()
