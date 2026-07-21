import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from config_manager import ConfigManager
from pomodoro import PomodoroStore, PomodoroTimer
from pomodoro_dialog import PomodoroController, PomodoroDialog


class PomodoroDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.now = datetime(2026, 7, 20, 9, 0, 0)
        self.timer = PomodoroTimer(
            store=PomodoroStore(Path(self.temp_dir.name) / "pomodoro.yaml"),
            now_provider=lambda: self.now,
        )
        self.config_manager = ConfigManager(
            str(Path(self.temp_dir.name) / "config.yaml")
        )
        self.controller = PomodoroController(
            self.timer,
            config_manager=self.config_manager,
        )
        self.dialog = PomodoroDialog(self.controller)

    def tearDown(self):
        self.controller.poll_timer.stop()
        self.dialog.close()

    def test_default_panel_state_and_settings(self):
        self.assertEqual(self.dialog._timer_label.text(), "25:00")
        self.assertEqual(self.dialog._primary_button.text(), "开始专注")
        self.assertTrue(self.dialog._hide_check.isChecked())
        self.assertFalse(self.dialog._auto_break_check.isChecked())
        self.assertEqual(self.dialog._stats_label.text(), "今天完成 0 轮  ·  专注 0 分钟")
        self.assertGreaterEqual(self.dialog.width(), self.dialog.sizeHint().width())

    def test_primary_button_starts_pauses_and_resumes(self):
        self.dialog._label_edit.setText("Finish report")

        self.dialog._on_primary()
        self.assertEqual(self.timer.snapshot()["status"], "running")
        self.assertEqual(self.timer.snapshot()["label"], "Finish report")
        self.assertEqual(self.dialog._primary_button.text(), "暂停")

        self.dialog._on_primary()
        self.assertEqual(self.timer.snapshot()["status"], "paused")
        self.assertEqual(self.dialog._primary_button.text(), "继续")

        self.dialog._on_primary()
        self.assertEqual(self.timer.snapshot()["status"], "running")

    def test_controller_emits_completion_event_and_updates_stats(self):
        events = []
        self.controller.event_emitted.connect(events.append)
        self.timer.start_focus(minutes=1)
        self.now += timedelta(minutes=1)

        self.controller.poll()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "focus_completed")
        self.assertEqual(self.dialog._timer_label.text(), "05:00")
        self.assertIn("今天完成 1 轮", self.dialog._stats_label.text())

    def test_settings_are_saved_to_main_config(self):
        self.dialog._focus_spin.setValue(45)
        self.dialog._short_break_spin.setValue(8)
        self.dialog._hide_check.setChecked(True)

        self.dialog._save_settings()

        saved = self.config_manager.load()["pomodoro"]
        self.assertEqual(saved["focus_minutes"], 45)
        self.assertEqual(saved["short_break_minutes"], 8)
        self.assertTrue(saved["hide_during_focus"])

    def test_progress_dimensions_remain_stable_while_ticking(self):
        size_before = self.dialog._progress.sizeHint()
        self.timer.start_focus(minutes=15)
        self.now += timedelta(minutes=5)
        self.controller.emit_state()

        self.assertEqual(self.dialog._timer_label.text(), "10:00")
        self.assertEqual(self.dialog._progress.sizeHint(), size_before)


if __name__ == "__main__":
    unittest.main()
