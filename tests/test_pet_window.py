import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from pet_window import PetWindow, clamp_to_available_screen


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

    def test_full_application_config_controls_window_behavior(self):
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()
        self.window = PetWindow({
            "pet": {"name": "Configured Pet"},
            "ui": {
                "window_size": 128,
                "wander_speed_ms": 7,
                "wander_x_range_ratio": 0.2,
            },
        })

        self.assertEqual(self.window.windowTitle(), "Configured Pet")
        self.assertEqual((self.window.width(), self.window.height()), (128, 128))
        self.assertEqual(self.window._wander_x_range_ratio, 0.2)

        self.window._toggle_quiet_mode(False)

        self.assertEqual(self.window.wander_timer.interval(), 7)

    def test_notify_only_does_not_force_animation_or_movement(self):
        original_position = self.window.pos()

        self.window.trigger_reminder({
            "name": "Notification",
            "message": "Message",
            "action_type": "notify_only",
            "sound": False,
        })

        self.assertTrue(self.window._quiet_mode)
        self.assertFalse(self.window.wander_timer.isActive())
        self.assertEqual(self.window.pos(), original_position)

    def test_interaction_dialog_calls_engine_action(self):
        engine = Mock()
        self.window._engine = engine

        self.window._show_reminder_interaction({"name": "Task", "message": "Do it"})
        dialog = self.window._interaction_dialogs[0]
        dialog._snooze(10)

        engine.handle_snooze.assert_called_once_with("Task", 10)
        self.assertEqual(self.window._interaction_dialogs, [])

    def test_window_is_clamped_to_available_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.window.move(screen.right() + 500, screen.bottom() + 500)

        clamp_to_available_screen(self.window)

        self.assertGreaterEqual(self.window.x(), screen.left())
        self.assertGreaterEqual(self.window.y(), screen.top())
        self.assertLessEqual(
            self.window.x() + self.window.width(), screen.right() + 1
        )
        self.assertLessEqual(
            self.window.y() + self.window.height(), screen.bottom() + 1
        )

    def test_disabled_weather_config_disables_tray_action(self):
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()
        self.window = PetWindow({
            "pet": {"name": "Weather Test"},
            "weather": {"enabled": False},
        })

        self.assertFalse(self.window._weather_action.isEnabled())


if __name__ == "__main__":
    unittest.main()
