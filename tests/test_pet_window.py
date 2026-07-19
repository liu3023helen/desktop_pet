import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from pet_window import PetWindow


class PetWindowModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = PetWindow({"name": "Test Pet"})

    def tearDown(self):
        self.window.wander_timer.stop()
        self.window.animation_player.stop()
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()

    def test_mode_toggle_round_trip_updates_behavior(self):
        self.assertTrue(self.window._quiet_mode)
        self.assertFalse(self.window.wander_timer.isActive())

        self.window._toggle_quiet_mode(False)

        self.assertFalse(self.window._quiet_mode)
        self.assertTrue(self.window.wander_timer.isActive())
        self.assertEqual(self.window._velocity, self.window._original_velocity)

        self.window._toggle_quiet_mode(True)

        self.assertTrue(self.window._quiet_mode)
        self.assertFalse(self.window.wander_timer.isActive())
        self.assertEqual((self.window._velocity.x(), self.window._velocity.y()), (0, 0))


if __name__ == "__main__":
    unittest.main()
