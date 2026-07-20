import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from pending_reminder_store import PendingReminderStore
from pet_window import PetWindow, clamp_to_available_screen


class PetWindowModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.now = datetime(2026, 7, 20, 12, 0, 0)
        self.store = PendingReminderStore(
            Path(self.temp_dir.name) / "pending.yaml"
        )
        self.window = self._create_window({"name": "Test Pet"})

    def _create_window(self, config):
        return PetWindow(
            config,
            pending_store=self.store,
            now_provider=lambda: self.now,
        )

    def tearDown(self):
        self.window.pending_reminder_timer.stop()
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
        self.window = self._create_window({
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

    def test_animation_reminder_temporarily_shows_tray_hidden_pet(self):
        engine = Mock()
        self.window._engine = engine
        self.window.show()
        self.window._hide_to_tray()

        self.window.trigger_reminder({
            "id": "tray-animation",
            "name": "Tray animation",
            "message": "Show the pet",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": False,
        })
        self.app.processEvents()

        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window._hidden_to_tray)

        self.window._handle_bubble_action("acknowledge")
        self.app.processEvents()

        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window._hidden_to_tray)

    def test_animation_reminder_keeps_normally_visible_pet_visible(self):
        self.window.show()

        self.window.trigger_reminder({
            "id": "visible-animation",
            "name": "Visible animation",
            "message": "Stay visible",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": False,
        })
        self.window._handle_bubble_action("acknowledge")
        self.app.processEvents()

        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window._hidden_to_tray)

    def test_tray_hidden_pet_stays_visible_until_reminder_queue_drains(self):
        self.window.show()
        self.window._hide_to_tray()
        for reminder_id in ("queued-first", "queued-second"):
            self.window.trigger_reminder({
                "id": reminder_id,
                "name": reminder_id,
                "message": reminder_id,
                "action_type": "play_animation",
                "animation": "cheer",
                "sound": False,
            })

        self.window._handle_bubble_action("acknowledge")
        self.app.processEvents()

        self.assertEqual(self.window._active_reminder["id"], "queued-second")
        self.assertTrue(self.window.isVisible())

        self.window._handle_bubble_action("acknowledge")
        self.app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_reminder_bubble_snooze_stops_animation_and_restores_quiet_mode(self):
        engine = Mock()
        self.window._engine = engine

        self.window.trigger_reminder({
            "id": "task-id",
            "name": "Task",
            "message": "Do it",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": False,
        })
        self.assertEqual(self.window.bubble.mode, "reminder")
        self.assertFalse(self.window._quiet_mode)

        self.window._handle_bubble_action("snooze_10")

        engine.handle_snooze.assert_not_called()
        self.assertTrue(self.window._quiet_mode)
        self.assertEqual(self.window.bubble.mode, "hidden")
        self.assertIsNone(self.window._active_reminder)
        stored = self.store.load(now=self.now)
        self.assertEqual(stored[0]["status"], "snoozed")

        self.now += timedelta(minutes=10)
        self.window._process_pending_reminders()

        self.assertEqual(self.window.bubble.mode, "reminder")
        self.assertEqual(self.window._active_reminder["id"], "task-id")
        self.assertFalse(self.window._quiet_mode)

    def test_reminder_bubble_acknowledge_completes_immediately(self):
        engine = Mock()
        self.window._engine = engine
        self.window.trigger_reminder({
            "_runtime_id": "runtime-id",
            "name": "Task",
            "message": "Do it",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": False,
        })

        self.window._handle_bubble_action("acknowledge")

        engine.handle_complete.assert_called_once_with("runtime-id")
        self.assertTrue(self.window._quiet_mode)
        self.assertFalse(self.window.animation_player.is_playing())
        self.assertEqual(self.window.bubble.mode, "hidden")

    def test_real_button_mouse_click_runs_snooze_end_to_end(self):
        self.window.trigger_reminder({
            "id": "mouse-click",
            "name": "Mouse click",
            "message": "Click me",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": False,
        })
        self.app.processEvents()

        QTest.mouseClick(
            self.window.bubble._snooze_button,
            Qt.LeftButton,
        )
        self.app.processEvents()

        self.assertEqual(self.window.bubble.mode, "hidden")
        self.assertIsNone(self.window._active_record)
        self.assertTrue(self.window._quiet_mode)
        self.assertEqual(
            self.store.load(now=self.now)[0]["status"],
            "snoozed",
        )

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
        self.window = self._create_window({
            "pet": {"name": "Weather Test"},
            "weather": {"enabled": False},
        })

        self.assertFalse(self.window._weather_action.isEnabled())

    def test_diagnostics_entry_starts_async_check_with_config_manager(self):
        config_manager = Mock()
        worker = Mock()
        worker.is_alive.return_value = False
        self.window._config_mgr = config_manager

        with patch(
            "diagnostics.run_diagnostics_async", return_value=worker
        ) as run_async:
            self.window._run_diagnostics()

        self.assertIs(self.window._diagnostics_thread, worker)
        self.assertIs(run_async.call_args.args[0], config_manager)
        self.assertTrue(callable(run_async.call_args.args[1]))
        self.assertEqual(self.window.bubble.mode, "loading")
        self.assertEqual(self.window.bubble.text(), "正在运行自检...")

        callback = run_async.call_args.args[1]
        callback("自检完成", True, ["配置正常", "素材正常"])
        self.assertEqual(self.window.bubble.mode, "result")
        self.assertIn("自检完成", self.window.bubble.text())

    def test_weather_query_starts_with_loading_bubble(self):
        self.window._config_mgr = Mock()
        self.window._config_mgr.load.return_value = {
            "weather": {"enabled": True, "city": "北京"}
        }

        with patch("threading.Thread") as thread_type:
            self.window._show_weather()

        thread_type.assert_called_once()
        self.assertEqual(self.window.bubble.mode, "loading")
        self.assertEqual(self.window.bubble.text(), "正在获取 北京 的天气...")

    def test_time_sync_starts_with_loading_bubble(self):
        self.window._config_mgr = Mock()
        self.window._config_mgr.load.return_value = {
            "time_sync": {
                "ntp_server": "ntp.aliyun.com",
                "tolerance_seconds": 30,
            }
        }

        with patch("threading.Thread") as thread_type:
            self.window._sync_time_now()

        thread_type.assert_called_once()
        self.assertEqual(self.window.bubble.mode, "loading")
        self.assertEqual(self.window.bubble.text(), "正在校准网络时间...")

    def test_configured_default_animation_is_used(self):
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()
        self.window = self._create_window({
            "pet": {"name": "Walker", "default_animation": "walk"},
        })

        self.assertEqual(self.window._default_animation, "walk")
        self.assertTrue(self.window.animation_player.is_animation_loaded("walk"))

    def test_missing_default_animation_falls_back_to_cheer(self):
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()
        self.window = self._create_window({
            "pet": {"name": "Fallback", "default_animation": "missing"},
        })

        self.assertEqual(self.window._default_animation, "cheer")
        self.assertTrue(self.window.animation_player.is_animation_loaded("cheer"))

    def test_reminders_are_persisted_and_presented_in_fifo_order(self):
        engine = Mock()
        self.window._engine = engine
        first = {
            "id": "first",
            "name": "First",
            "message": "First message",
            "action_type": "notify_only",
            "sound": False,
        }
        second = {
            "id": "second",
            "name": "Second",
            "message": "Second message",
            "action_type": "notify_only",
            "sound": False,
        }

        self.window.trigger_reminder(first)
        self.window.trigger_reminder(second)

        self.assertEqual(self.window._active_reminder["id"], "first")
        self.assertEqual(len(self.store.load(now=self.now)), 2)

        self.window._handle_bubble_action("acknowledge")

        self.assertEqual(self.window._active_reminder["id"], "second")
        self.assertEqual(self.window.bubble.text(), "Second message")

        self.window._handle_bubble_action("acknowledge")

        self.assertEqual(
            [call.args[0] for call in engine.handle_complete.call_args_list],
            ["first", "second"],
        )
        self.assertEqual(self.store.load(now=self.now), [])

    def test_pending_reminder_is_restored_after_window_restart(self):
        self.window.trigger_reminder({
            "id": "restart",
            "name": "Restart",
            "message": "Still pending",
            "action_type": "notify_only",
            "sound": False,
        })
        self.window.pending_reminder_timer.stop()
        self.window.bubble.close()
        self.window.tray_icon.hide()
        self.window.close()

        self.window = self._create_window({"name": "Test Pet"})

        self.assertEqual(self.window._active_reminder["id"], "restart")
        self.assertEqual(self.window.bubble.mode, "reminder")
        self.assertEqual(self.window.bubble.text(), "Still pending")

    def test_scheduled_trigger_time_is_used_for_persisted_fifo_order(self):
        self.window.trigger_reminder({
            "id": "scheduled",
            "name": "Scheduled",
            "message": "Scheduled message",
            "action_type": "notify_only",
            "sound": False,
            "_triggered_at": "2026-07-20T09:30:00",
        })

        stored = self.store.load(now=self.now)

        self.assertEqual(stored[0]["triggered_at"], "2026-07-20T09:30:00")
        self.assertNotIn("_triggered_at", stored[0]["reminder"])

    def test_locked_pending_reminder_expires_from_memory_after_24_hours(self):
        self.window.set_session_locked(True)
        self.window.trigger_reminder({
            "id": "expires",
            "name": "Expires",
            "message": "Too old",
            "action_type": "notify_only",
            "sound": False,
        })
        self.assertEqual(len(self.window._pending_records), 1)

        self.now += timedelta(hours=24, seconds=1)
        self.window._process_pending_reminders()

        self.assertEqual(self.window._pending_records, [])
        self.assertEqual(self.store.load(now=self.now), [])

        self.window.set_session_locked(False)

        self.assertIsNone(self.window._active_record)
        self.assertEqual(self.window.bubble.mode, "hidden")

    def test_utility_result_waits_until_active_reminder_is_closed(self):
        self.window.trigger_reminder({
            "id": "priority",
            "name": "Priority",
            "message": "Handle me first",
            "action_type": "notify_only",
            "sound": False,
        })

        self.window._show_status_result("天气查询完成")

        self.assertEqual(self.window.bubble.mode, "reminder")
        self.assertEqual(self.window.bubble.text(), "Handle me first")

        self.window._handle_bubble_action("acknowledge")

        self.assertEqual(self.window.bubble.mode, "result")
        self.assertEqual(self.window.bubble.text(), "天气查询完成")

    @patch("pet_window.play_reminder_sound")
    def test_lock_hides_active_reminder_and_unlock_resumes_without_sound(
        self,
        play_sound,
    ):
        self.window.trigger_reminder({
            "id": "active-at-lock",
            "name": "Active",
            "message": "Resume me",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": True,
        })
        self.assertEqual(play_sound.call_count, 1)

        self.window.set_session_locked(True)

        self.assertEqual(self.window.bubble.mode, "hidden")
        self.assertTrue(self.window._quiet_mode)
        self.assertIsNotNone(self.window._active_record)

        self.window.set_session_locked(False)

        self.assertEqual(self.window.bubble.mode, "reminder")
        self.assertEqual(self.window.bubble.text(), "Resume me")
        self.assertFalse(self.window._quiet_mode)
        self.assertEqual(play_sound.call_count, 1)

    @patch("pet_window.play_reminder_sound")
    def test_reminders_triggered_while_locked_wait_for_unlock(self, play_sound):
        self.window.set_session_locked(True)

        self.window.trigger_reminder({
            "id": "locked-first",
            "name": "First",
            "message": "First after unlock",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": True,
        })
        self.window.trigger_reminder({
            "id": "locked-second",
            "name": "Second",
            "message": "Second after unlock",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": True,
        })

        self.assertIsNone(self.window._active_record)
        self.assertEqual(self.window.bubble.mode, "hidden")
        self.assertTrue(self.window._quiet_mode)
        self.assertEqual(len(self.store.load(now=self.now)), 2)
        play_sound.assert_not_called()

        self.window.set_session_locked(False)

        self.assertEqual(self.window._active_reminder["id"], "locked-first")
        self.assertEqual(self.window.bubble.text(), "First after unlock")
        play_sound.assert_called_once_with(None)

        self.window._handle_bubble_action("acknowledge")

        self.assertEqual(self.window._active_reminder["id"], "locked-second")
        self.assertEqual(play_sound.call_count, 2)

        self.window.set_session_locked(True)
        self.window.set_session_locked(False)

        self.assertEqual(play_sound.call_count, 2)

    @patch("pet_window.play_reminder_sound")
    def test_snooze_due_while_locked_sounds_once_after_unlock(self, play_sound):
        self.window.trigger_reminder({
            "id": "locked-snooze",
            "name": "Snooze",
            "message": "Snoozed reminder",
            "action_type": "play_animation",
            "animation": "cheer",
            "sound": True,
        })
        self.window._handle_bubble_action("snooze_10")
        self.window.set_session_locked(True)
        self.now += timedelta(minutes=10)

        self.window._process_pending_reminders()

        self.assertIsNone(self.window._active_record)
        self.assertEqual(play_sound.call_count, 1)

        self.window.set_session_locked(False)

        self.assertEqual(self.window._active_reminder["id"], "locked-snooze")
        self.assertEqual(play_sound.call_count, 2)

        self.window.set_session_locked(True)
        self.window.set_session_locked(False)

        self.assertEqual(play_sound.call_count, 2)


if __name__ == "__main__":
    unittest.main()
